import React, { useState, useEffect } from "react";
import axios from "axios";
import Button from "./components/Button";
import Loader from "./components/Loader";
import EmptyState from "./components/EmptyState";

// Helper function to sanitize CSV data for display
const sanitizeCSVData = (data) => {
  if (!Array.isArray(data) || data.length === 0) {
    return [];
  }
  
  try {
    // Clean any potential NaN values in the data
    return data.map(row => {
      const cleanRow = {};
      Object.keys(row).forEach(key => {
        const value = row[key];
        // Handle NaN, null, undefined, and other problematic values
        cleanRow[key] = (value === null || value === undefined || 
                       (typeof value === 'number' && isNaN(value))) ? '' : value;
      });
      return cleanRow;
    });
  } catch (error) {
    console.error("Error sanitizing CSV data:", error);
    return [];
  }
};

function App() {
  const [file, setFile] = useState(null);
  const [filename, setFilename] = useState("");
  const [resultFile, setResultFile] = useState("");
  const [preview, setPreview] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [backendStatus, setBackendStatus] = useState("checking");

  // Check backend connection and health on component mount
  useEffect(() => {
    const checkBackendConnection = async () => {
      try {
        const response = await axios.get("http://127.0.0.1:8000/ping");
        if (response.data.status === "healthy") {
          setBackendStatus("connected");
        } else {
          setBackendStatus("unhealthy");
          setError(`Backend server is running but unhealthy: ${response.data.error || 'Unknown issue'}.`);
        }
      } catch (err) {
        setBackendStatus("disconnected");
        setError("Cannot connect to backend server. Please ensure it's running at http://127.0.0.1:8000.");
      }
    };
    
    checkBackendConnection();
    
    // Set up periodic health checks every 30 seconds
    const healthCheckInterval = setInterval(checkBackendConnection, 30000);
    
    // Clean up interval on component unmount
    return () => clearInterval(healthCheckInterval);
  }, []);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await axios.post("http://127.0.0.1:8000/upload/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setFilename(res.data.filename);
    } catch (err) {
      console.error("Upload error:", err);
      
      // Format error message for better user experience
      let errorMessage = err.response?.data?.detail || err.message || 'An error occurred during upload';
      
      // Check for specific CSV errors and provide more helpful messages
      if (errorMessage.includes("NaN") || errorMessage.includes("nan")) {
        errorMessage = "Your CSV file contains invalid numeric values (NaN). Please clean your data before uploading.";
      } else if (errorMessage.includes("parsing error")) {
        errorMessage = "Your CSV file has formatting issues. Please check for missing commas, quotes, or invalid characters.";
      } else if (errorMessage.includes("LinkedIn URL")) {
        errorMessage = "Your CSV file must contain a column with LinkedIn URLs. Valid column names are: LinkedIn URL, linkedin_url, Profile URL, LinkedIn, or linkedin.";
      }
      
      setError(errorMessage);
      setFilename(""); // Clear filename if there was an error
    } finally {
      setLoading(false);
    }
  };

  const handleProcess = async () => {
    if (!filename) return;
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("filename", filename);
      const res = await axios.post("http://127.0.0.1:8000/process/", formData);
      setResultFile(res.data.result_file);
      await handlePreview(res.data.result_file);
    } catch (err) {
      console.error("Process error:", err);
      setError(err.response?.data?.detail || err.message || 'An error occurred during processing');
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (file) => {
    try {
      const res = await axios.get(`http://127.0.0.1:8000/preview/${file}`);
      
      // Use the sanitizeCSVData helper function to clean the data
      const cleanedData = sanitizeCSVData(res.data);
      
      if (cleanedData.length > 0) {
        setPreview(cleanedData);
      } else {
        setPreview([]);
        if (Array.isArray(res.data) && res.data.length === 0) {
          setError('The CSV file appears to be empty.');
        } else if (!Array.isArray(res.data)) {
          setError('Invalid data format received from server.');
        }
      }
    } catch (err) {
      console.error("Preview error:", err);
      setPreview([]);
      setError(err.response?.data?.detail || err.message || 'An error occurred while loading preview');
    }
  };

  const handleDownload = () => {
    window.open(`http://127.0.0.1:8000/download/${resultFile}`);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center p-8">
      <h1 className="text-3xl font-bold mb-6">LinkedIn Prospect Filter</h1>
      
      {(backendStatus === "disconnected" || backendStatus === "unhealthy") && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4 w-full max-w-xl">
          <p className="font-bold">
            {backendStatus === "disconnected" ? "Backend Connection Error" : "Backend Health Issue"}
          </p>
          <p>{error}</p>
        </div>
      )}
      
      <div className="bg-white p-6 rounded shadow w-full max-w-xl flex flex-col gap-4">
        <input type="file" accept=".csv" onChange={handleFileChange} />
        {error && (
          <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}
        {loading ? <Loader /> : (
          <>
            <Button 
              variant="primary" 
              onClick={handleUpload} 
              disabled={loading || backendStatus === "disconnected" || backendStatus === "unhealthy"}
            >
              Upload CSV
            </Button>
            <Button 
              variant="secondary" 
              onClick={handleProcess} 
              disabled={!filename || loading || backendStatus === "disconnected" || backendStatus === "unhealthy"}
            >
              Process & Classify
            </Button>
            {resultFile && (
              <Button 
                variant="success" 
                onClick={handleDownload}
                disabled={backendStatus === "disconnected" || backendStatus === "unhealthy"}
              >
                Download Filtered CSV
              </Button>
            )}
          </>
        )}
      </div>
      {preview.length > 0 ? (
        <div className="mt-8 w-full max-w-4xl">
          <h2 className="text-xl font-semibold mb-2">Preview (first 100 rows)</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full bg-white rounded shadow">
              <thead>
                <tr>
                  {(() => {
                    try {
                      return Object.keys(preview[0]).map((col) => (
                        <th key={col} className="px-2 py-1 border-b text-xs text-gray-700">{col}</th>
                      ));
                    } catch (err) {
                      console.error("Error rendering table headers:", err);
                      return <th className="px-2 py-1 border-b text-xs text-gray-700">Error loading headers</th>;
                    }
                  })()}
                </tr>
              </thead>
              <tbody>
                {preview.map((row, i) => {
                  return (() => {
                    try {
                      return (
                        <tr key={i} className="hover:bg-gray-100">
                          {Object.values(row).map((val, j) => (
                            <td key={j} className="px-2 py-1 border-b text-xs">
                              {val === null || val === undefined || (typeof val === 'number' && isNaN(val)) ? '' : val}
                            </td>
                          ))}
                        </tr>
                      );
                    } catch (err) {
                      console.error(`Error rendering row ${i}:`, err);
                      return (
                        <tr key={i} className="hover:bg-gray-100 bg-red-50">
                          <td colSpan="100%" className="px-2 py-1 border-b text-xs text-red-500">
                            Error rendering row {i+1}
                          </td>
                        </tr>
                      );
                    }
                  })();
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}

export default App;