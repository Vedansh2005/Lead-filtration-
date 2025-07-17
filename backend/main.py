from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import logging
import numpy as np
from linkedin_utils import validate_linkedin_profile

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Utility function to sanitize DataFrames for JSON compatibility
def sanitize_dataframe(df):
    """
    Sanitize a DataFrame to ensure it's compatible with JSON serialization.
    - Replace NaN values with None (for JSON) or empty strings (for CSV)
    - Convert any problematic data types
    """
    # Make a copy to avoid modifying the original
    df_clean = df.copy()
    
    # Replace NaN/None values with empty strings
    df_clean = df_clean.fillna('')
    
    # Replace any remaining NaN values (that might come from calculations)
    for col in df_clean.columns:
        if df_clean[col].dtype == np.float64 or df_clean[col].dtype == np.float32:
            df_clean[col] = df_clean[col].replace([np.inf, -np.inf, np.nan], '')
    
    logger.info("DataFrame sanitized for JSON/CSV compatibility")
    return df_clean

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

def check_csv_issues(file_path):
    """Check for common issues in CSV files"""
    try:
        # Try to read the CSV file
        df = pd.read_csv(file_path)
        
        # Check for empty file
        if df.empty:
            return "The CSV file is empty."
        
        # Check for NaN values
        nan_count = df.isna().sum().sum()
        if nan_count > 0:
            logger.warning(f"CSV contains {nan_count} NaN values, will be sanitized")
        
        # Check for LinkedIn URL column
        linkedin_cols = ["linkedinUrl"]
        has_linkedin_col = any(col in df.columns for col in linkedin_cols)
        if not has_linkedin_col:
            return "CSV file does not contain a LinkedIn URL column. Please include one of these columns: LinkedIn URL, linkedin_url, Profile URL, LinkedIn, linkedin."
        
        # Check for valid LinkedIn URLs
        for col in linkedin_cols:
            if col in df.columns:
                valid_urls = df[col].apply(lambda x: isinstance(x, str) and x.startswith('http')).sum()
                if valid_urls == 0:
                    return f"No valid LinkedIn URLs found in the '{col}' column. URLs should start with 'http'."
                break
        
        return None  # No issues found
    except pd.errors.EmptyDataError:
        return "The CSV file is empty."
    except pd.errors.ParserError as e:
        return f"CSV parsing error: {str(e)}"
    except Exception as e:
        logger.error(f"Error checking CSV issues: {str(e)}")
        return f"Error validating CSV: {str(e)}"
    
@app.post("/upload/")
async def upload_csv(file: UploadFile = File(...)):
    try:
        logger.info(f"Received file upload: {file.filename}")
        if not file.filename.endswith('.csv'):
            logger.warning(f"Invalid file type: {file.filename}")
            raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
        
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_location, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"File saved to: {file_location}")
        
        # Check for common CSV issues
        issues = check_csv_issues(file_location)
        if issues:
            logger.warning(f"CSV validation failed: {issues}")
            raise HTTPException(status_code=400, detail=issues)
        
        return {"filename": file.filename}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during file upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
@app.post("/process/")
async def process_csv(background_tasks: BackgroundTasks, filename: str = Form(...)):
    try:
        logger.info(f"Processing file: {filename}")
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found.")
        
        try:
            # Read CSV with more robust error handling
            try:
                # First try with default settings
                df = pd.read_csv(file_path)
            except pd.errors.ParserError as e:
                logger.warning(f"Standard parsing failed, trying with error_bad_lines=False: {str(e)}")
                # If that fails, try with error_bad_lines=False (skip bad lines)
                try:
                    # For pandas < 1.3.0
                    df = pd.read_csv(file_path, error_bad_lines=False)
                except TypeError:
                    # For pandas >= 1.3.0
                    df = pd.read_csv(file_path, on_bad_lines='skip')
                logger.info("Successfully read CSV with bad lines skipped")
            
            # Sanitize the DataFrame
            df = sanitize_dataframe(df)
            logger.info(f"Successfully read CSV with {len(df)} rows")
            
            # Check if we have enough data to process
            if len(df) == 0:
                raise ValueError("CSV file contains no valid data rows after cleaning")
            
        except Exception as e:
            logger.error(f"Error reading CSV: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid CSV: {str(e)}")
        
        # Process in background to avoid timeout
        result_path = os.path.join(RESULTS_DIR, f"processed_{filename}")
        background_tasks.add_task(process_profiles, df, result_path)
        
        return {"result_file": f"processed_{filename}", "status": "processing"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

def process_profiles(df, result_path):
    try:
        logger.info("Starting profile validation")
        # Prepare a list to collect valid rows
        valid_rows = []
        for idx, row in df.iterrows():
            url = None
            # Try different column names for LinkedIn URL
            for col in ["linkedinUrl"]:
                if col in row and isinstance(row[col], str) and row[col].startswith("http"):
                    url = row[col]
                    break
            if not url:
                continue  # Skip rows without a valid URL
            try:
                logger.info(f"Validating profile {idx+1}/{len(df)}: {url}")
                result = validate_linkedin_profile(url)
                if result is None or not result.get("companies"):
                    continue  # Skip rows where validation fails, returns None, or no matching companies
                # Use the first matching company
                company = result["companies"][0]
                output_row = row.to_dict()
                output_row["lead_status"] = "valid" if result["has_photo"] and result["job_title"] else "invalid"
                output_row["profile_job_title"] = result["job_title"]
                output_row["profile_connections"] = result["connections"]
                output_row["company_url"] = company.get("company_url", "")
                output_row["company_about"] = company.get("about", "")
                output_row["product_category"] = ""  # Placeholder for future classification
                valid_rows.append(output_row)
            except Exception as e:
                logger.error(f"Error validating profile {url}: {str(e)}")
                # Skip this row on error
                continue
        # Create a new DataFrame only with valid rows
        if valid_rows:
            result_df = pd.DataFrame(valid_rows)
            # Sort by profile_job_title (or any other field you prefer)
            if "profile_job_title" in result_df.columns:
                result_df = result_df.sort_values(by=["profile_job_title"]).reset_index(drop=True)
            # Sanitize DataFrame before saving
            result_df = sanitize_dataframe(result_df)
            result_df.to_csv(result_path, index=False)
            logger.info(f"Processing complete, saved to {result_path}")
        else:
            # If no valid rows, save an empty file with headers
            df.head(0).to_csv(result_path, index=False)
            logger.info(f"No valid profiles found. Saved empty file to {result_path}")
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")

@app.get("/download/{result_file}")
def download_csv(result_file: str):
    try:
        logger.info(f"Download requested for: {result_file}")
        result_path = os.path.join(RESULTS_DIR, result_file)
        if not os.path.exists(result_path):
            logger.warning(f"Result file not found: {result_path}")
            raise HTTPException(status_code=404, detail="Result file not found.")
        return FileResponse(result_path, media_type='text/csv', filename=result_file)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.get("/preview/{result_file}")
def preview_csv(result_file: str):
    try:
        logger.info(f"Preview requested for: {result_file}")
        result_path = os.path.join(RESULTS_DIR, result_file)
        if not os.path.exists(result_path):
            logger.warning(f"Result file not found for preview: {result_path}")
            raise HTTPException(status_code=404, detail="Result file not found.")
        
        try:
            df = pd.read_csv(result_path)
            logger.info(f"Successfully read preview CSV with {len(df)} rows")
            
            # Sanitize DataFrame for JSON compatibility
            df = sanitize_dataframe(df)
            
            # Convert to dict for JSON response
            preview_data = df.head(100).to_dict(orient="records")
            
            return JSONResponse(preview_data)
        except Exception as e:
            logger.error(f"Error reading CSV for preview: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid CSV: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during preview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")

@app.get("/ping")
def ping():
    """Health check endpoint to verify the server is running properly"""
    try:
        # Test pandas and numpy functionality
        test_df = pd.DataFrame({"test": [1, np.nan, 3]})
        sanitized_df = sanitize_dataframe(test_df)
        
        # If we get here, everything is working correctly
        return {"message": "pong", "status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"message": "pong", "status": "unhealthy", "error": str(e)}