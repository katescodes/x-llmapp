import React, { useState, useEffect } from "react";

interface FeatureFlags {
  PLATFORM_JOBS_ENABLED: boolean;
  EVIDENCE_SPANS_ENABLED: boolean;
  DOCSTORE_DUALWRITE: boolean;
  REVIEWCASE_DUALWRITE: boolean;
  RULESET_PARSE_ENABLED: boolean;
  RULES_EVALUATOR_ENABLED: boolean;
  ASYNC_INGEST_ENABLED: boolean;
}

interface DebugData {
  feature_flags: FeatureFlags;
  environment: string;
  note: string;
}

interface PlatformJob {
  id: string;
  namespace: string;
  biz_type: string;
  biz_id: string;
  status: string;
  progress: number;
  message: string | null;
  result_json: any;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
}

interface JobsData {
  enabled: boolean;
  jobs: PlatformJob[];
  stats?: {
    total: number;
    by_status: Record<string, number>;
    by_biz_type: Record<string, number>;
  };
  message?: string;
}

interface ReviewCase {
  id: string;
  namespace: string;
  project_id: string;
  tender_doc_version_ids: string[];
  bid_doc_version_ids: string[];
  attachment_doc_version_ids: string[];
  created_at: string;
  runs: ReviewRun[];
}

interface ReviewRun {
  id: string;
  case_id: string;
  status: string;
  model_id: string | null;
  rule_set_version_id: string | null;
  result_json: any;
  created_at: string;
  updated_at: string;
  findings_stats: {
    total: number;
    by_result: Record<string, number>;
    by_source: Record<string, number>;
  };
  findings_sample: any[];
}

interface ReviewCasesData {
  enabled: boolean;
  cases: ReviewCase[];
  stats?: {
    total_cases: number;
    total_runs: number;
  };
  message?: string;
}

const DebugPanel: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [debugData, setDebugData] = useState<DebugData | null>(null);
  const [jobsData, setJobsData] = useState<JobsData | null>(null);
  const [reviewCasesData, setReviewCasesData] = useState<ReviewCasesData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"flags" | "jobs" | "review-cases">("flags");
  const [projectIdFilter, setProjectIdFilter] = useState<string>("");

  // 检查是否应该显示 Debug 面板
  const showDebug = import.meta.env.VITE_SHOW_DEBUG === "true";
  const isDev = import.meta.env.DEV;

  useEffect(() => {
    if (isOpen && !debugData && !loading) {
      fetchDebugData();
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && activeTab === "jobs" && !jobsData && !loading) {
      fetchJobsData();
    }
  }, [isOpen, activeTab]);

  useEffect(() => {
    if (isOpen && activeTab === "review-cases" && !loading) {
      fetchReviewCasesData();
    }
  }, [isOpen, activeTab, projectIdFilter]);

  const fetchDebugData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/_debug/flags");
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setDebugData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch debug data");
    } finally {
      setLoading(false);
    }
  };

  const fetchJobsData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/_debug/jobs?limit=50");
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setJobsData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch jobs data");
    } finally {
      setLoading(false);
    }
  };

  const fetchReviewCasesData = async () => {
    if (!projectIdFilter) {
      setReviewCasesData({
        enabled: true,
        message: "Please enter a project ID to search",
        cases: []
      });
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/_debug/review-cases?project_id=${encodeURIComponent(projectIdFilter)}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setReviewCasesData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch review cases data");
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    if (activeTab === "flags") {
      fetchDebugData();
    } else if (activeTab === "jobs") {
      fetchJobsData();
    } else if (activeTab === "review-cases") {
      fetchReviewCasesData();
    }
  };

  // 如果不应该显示 Debug 面板，直接返回 null
  if (!showDebug && !isDev) {
    return null;
  }

  return (
    <>
      {/* 浮动按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: "fixed",
          bottom: "20px",
          right: "20px",
          width: "50px",
          height: "50px",
          borderRadius: "50%",
          border: "2px solid rgba(79, 70, 229, 0.5)",
          background: "rgba(79, 70, 229, 0.9)",
          color: "#fff",
          fontSize: "24px",
          cursor: "pointer",
          zIndex: 9998,
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "all 0.3s ease"
        }}
        title="Debug Panel"
      >
        🐛
      </button>

      {/* Debug 面板 */}
      {isOpen && (
        <div
          style={{
            position: "fixed",
            bottom: "80px",
            right: "20px",
            width: "400px",
            maxHeight: "600px",
            background: "rgba(15, 23, 42, 0.98)",
            border: "1px solid rgba(79, 70, 229, 0.3)",
            borderRadius: "12px",
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.5)",
            zIndex: 9999,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column"
          }}
        >
          {/* 标题栏 */}
          <div
            style={{
              padding: "16px",
              borderBottom: "1px solid rgba(79, 70, 229, 0.3)",
              background: "rgba(79, 70, 229, 0.1)"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 style={{ margin: 0, color: "#e5e7eb", fontSize: "16px", fontWeight: "600" }}>
                🐛 Debug Panel
              </h3>
              <button
                onClick={() => setIsOpen(false)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#e5e7eb",
                  fontSize: "20px",
                  cursor: "pointer",
                  padding: "0",
                  width: "24px",
                  height: "24px"
                }}
              >
                ×
              </button>
            </div>
            {/* Tabs */}
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                onClick={() => setActiveTab("flags")}
                style={{
                  padding: "6px 12px",
                  border: "none",
                  background: activeTab === "flags" ? "rgba(79, 70, 229, 0.3)" : "rgba(79, 70, 229, 0.1)",
                  color: "#e5e7eb",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontSize: "13px"
                }}
              >
                🚩 Flags
              </button>
              <button
                onClick={() => setActiveTab("jobs")}
                style={{
                  padding: "6px 12px",
                  border: "none",
                  background: activeTab === "jobs" ? "rgba(79, 70, 229, 0.3)" : "rgba(79, 70, 229, 0.1)",
                  color: "#e5e7eb",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontSize: "13px"
                }}
              >
                ⚙️ Jobs
              </button>
              <button
                onClick={() => setActiveTab("review-cases")}
                style={{
                  padding: "6px 12px",
                  border: "none",
                  background: activeTab === "review-cases" ? "rgba(79, 70, 229, 0.3)" : "rgba(79, 70, 229, 0.1)",
                  color: "#e5e7eb",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontSize: "13px"
                }}
              >
                📋 Review
              </button>
            </div>
          </div>

          {/* 内容区 */}
          <div
            style={{
              padding: "16px",
              overflowY: "auto",
              flex: 1,
              color: "#e5e7eb",
              fontSize: "13px"
            }}
          >
            {loading && (
              <div style={{ textAlign: "center", padding: "20px", color: "#94a3b8" }}>
                Loading...
              </div>
            )}

            {error && (
              <div
                style={{
                  padding: "12px",
                  background: "rgba(239, 68, 68, 0.1)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: "6px",
                  color: "#fca5a5"
                }}
              >
                <strong>Error:</strong> {error}
              </div>
            )}

            {activeTab === "flags" && debugData && (
              <>
                {/* 环境信息 */}
                <div style={{ marginBottom: "16px" }}>
                  <div style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "8px" }}>
                    Environment
                  </div>
                  <div
                    style={{
                      padding: "8px 12px",
                      background: "rgba(79, 70, 229, 0.1)",
                      borderRadius: "6px",
                      fontFamily: "monospace"
                    }}
                  >
                    {debugData.environment}
                  </div>
                </div>

                {/* Feature Flags */}
                <div style={{ marginBottom: "16px" }}>
                  <div style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "8px" }}>
                    Feature Flags
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    {Object.entries(debugData.feature_flags).map(([key, value]) => (
                      <div
                        key={key}
                        style={{
                          padding: "8px 12px",
                          background: "rgba(30, 41, 59, 0.5)",
                          borderRadius: "6px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center"
                        }}
                      >
                        <span style={{ fontFamily: "monospace", fontSize: "12px" }}>{key}</span>
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: "4px",
                            fontSize: "11px",
                            fontWeight: "600",
                            background: value
                              ? "rgba(34, 197, 94, 0.2)"
                              : "rgba(148, 163, 184, 0.2)",
                            color: value ? "#86efac" : "#cbd5e1"
                          }}
                        >
                          {value ? "ON" : "OFF"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 注意事项 */}
                <div
                  style={{
                    padding: "12px",
                    background: "rgba(59, 130, 246, 0.1)",
                    border: "1px solid rgba(59, 130, 246, 0.3)",
                    borderRadius: "6px",
                    fontSize: "12px",
                    color: "#93c5fd"
                  }}
                >
                  <strong>Note:</strong> {debugData.note}
                </div>
              </>
            )}

            {activeTab === "jobs" && jobsData && (
              <>
                {!jobsData.enabled ? (
                  <div
                    style={{
                      padding: "20px",
                      textAlign: "center",
                      color: "#94a3b8",
                      background: "rgba(148, 163, 184, 0.1)",
                      borderRadius: "6px"
                    }}
                  >
                    <div style={{ fontSize: "32px", marginBottom: "12px" }}>⚠️</div>
                    <div style={{ fontSize: "14px", marginBottom: "8px" }}>Platform Jobs Disabled</div>
                    <div style={{ fontSize: "12px" }}>
                      Set <code style={{ background: "rgba(79, 70, 229, 0.2)", padding: "2px 6px", borderRadius: "3px" }}>PLATFORM_JOBS_ENABLED=true</code> to view jobs
                    </div>
                  </div>
                ) : (
                  <>
                    {/* 统计信息 */}
                    {jobsData.stats && (
                      <div style={{ marginBottom: "16px" }}>
                        <div style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "8px" }}>
                          Statistics
                        </div>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          <div style={{ padding: "6px 12px", background: "rgba(79, 70, 229, 0.1)", borderRadius: "4px", fontSize: "12px" }}>
                            Total: {jobsData.stats.total}
                          </div>
                          {Object.entries(jobsData.stats.by_status).map(([status, count]) => (
                            <div
                              key={status}
                              style={{
                                padding: "6px 12px",
                                background: status === "succeeded" ? "rgba(34, 197, 94, 0.1)" : 
                                           status === "failed" ? "rgba(239, 68, 68, 0.1)" :
                                           status === "running" ? "rgba(59, 130, 246, 0.1)" :
                                           "rgba(148, 163, 184, 0.1)",
                                borderRadius: "4px",
                                fontSize: "12px"
                              }}
                            >
                              {status}: {count}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Jobs 列表 */}
                    <div style={{ marginBottom: "16px" }}>
                      <div style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "8px" }}>
                        Recent Jobs ({jobsData.jobs.length})
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "400px", overflowY: "auto" }}>
                        {jobsData.jobs.length === 0 ? (
                          <div style={{ padding: "20px", textAlign: "center", color: "#94a3b8", fontSize: "13px" }}>
                            No jobs found
                          </div>
                        ) : (
                          jobsData.jobs.map((job) => (
                            <div
                              key={job.id}
                              style={{
                                padding: "10px",
                                background: "rgba(30, 41, 59, 0.5)",
                                borderRadius: "6px",
                                border: "1px solid rgba(79, 70, 229, 0.2)"
                              }}
                            >
                              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                                <span style={{ fontSize: "12px", color: "#e5e7eb", fontWeight: "600" }}>
                                  {job.biz_type}
                                </span>
                                <span
                                  style={{
                                    padding: "2px 6px",
                                    borderRadius: "3px",
                                    fontSize: "10px",
                                    fontWeight: "600",
                                    background: job.status === "succeeded" ? "rgba(34, 197, 94, 0.2)" :
                                               job.status === "failed" ? "rgba(239, 68, 68, 0.2)" :
                                               job.status === "running" ? "rgba(59, 130, 246, 0.2)" :
                                               "rgba(148, 163, 184, 0.2)",
                                    color: job.status === "succeeded" ? "#86efac" :
                                           job.status === "failed" ? "#fca5a5" :
                                           job.status === "running" ? "#93c5fd" :
                                           "#cbd5e1"
                                  }}
                                >
                                  {job.status}
                                </span>
                              </div>
                              <div style={{ fontSize: "11px", color: "#94a3b8", marginBottom: "4px" }}>
                                ID: {job.id}
                              </div>
                              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                                <span>Progress: {job.progress}%</span>
                                <span>{new Date(job.created_at).toLocaleString()}</span>
                              </div>
                              {job.message && (
                                <div style={{ marginTop: "6px", fontSize: "11px", color: "#cbd5e1", fontStyle: "italic" }}>
                                  {job.message}
                                </div>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </>
                )}
              </>
            )}

            {activeTab === "review-cases" && (
              <>
                {/* Project ID 过滤器 */}
                <div style={{ marginBottom: "16px" }}>
                  <div style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "8px" }}>
                    Project ID
                  </div>
                  <input
                    type="text"
                    value={projectIdFilter}
                    onChange={(e) => setProjectIdFilter(e.target.value)}
                    placeholder="Enter project ID (e.g., tp_xxx)"
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      background: "rgba(30, 41, 59, 0.5)",
                      border: "1px solid rgba(79, 70, 229, 0.3)",
                      borderRadius: "6px",
                      color: "#e5e7eb",
                      fontSize: "13px",
                      fontFamily: "monospace"
                    }}
                  />
                </div>

                {reviewCasesData && !reviewCasesData.enabled && (
                  <div
                    style={{
                      padding: "20px",
                      textAlign: "center",
                      color: "#94a3b8",
                      background: "rgba(148, 163, 184, 0.1)",
                      borderRadius: "6px"
                    }}
                  >
                    <div style={{ fontSize: "32px", marginBottom: "12px" }}>⚠️</div>
                    <div style={{ fontSize: "14px", marginBottom: "8px" }}>ReviewCase Disabled</div>
                    <div style={{ fontSize: "12px" }}>
                      Set <code style={{ background: "rgba(79, 70, 229, 0.2)", padding: "2px 6px", borderRadius: "3px" }}>REVIEWCASE_DUALWRITE=true</code> to view review cases
                    </div>
                  </div>
                )}

                {reviewCasesData && reviewCasesData.enabled && (
                  <>
                    {reviewCasesData.message && reviewCasesData.cases.length === 0 && (
                      <div
                        style={{
                          padding: "16px",
                          textAlign: "center",
                          color: "#94a3b8",
                          background: "rgba(148, 163, 184, 0.05)",
                          borderRadius: "6px",
                          fontSize: "13px"
                        }}
                      >
                        {reviewCasesData.message}
                      </div>
                    )}

                    {reviewCasesData.stats && reviewCasesData.cases.length > 0 && (
                      <div style={{ marginBottom: "16px" }}>
                        <div style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "8px" }}>
                          Statistics
                        </div>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          <div style={{ padding: "6px 12px", background: "rgba(79, 70, 229, 0.1)", borderRadius: "4px", fontSize: "12px" }}>
                            Cases: {reviewCasesData.stats.total_cases}
                          </div>
                          <div style={{ padding: "6px 12px", background: "rgba(34, 197, 94, 0.1)", borderRadius: "4px", fontSize: "12px" }}>
                            Runs: {reviewCasesData.stats.total_runs}
                          </div>
                        </div>
                      </div>
                    )}

                    {reviewCasesData.cases.length > 0 && (
                      <div style={{ marginBottom: "16px" }}>
                        <div style={{ color: "#94a3b8", fontSize: "12px", marginBottom: "8px" }}>
                          Review Cases ({reviewCasesData.cases.length})
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxHeight: "400px", overflowY: "auto" }}>
                          {reviewCasesData.cases.map((reviewCase) => (
                            <div
                              key={reviewCase.id}
                              style={{
                                padding: "12px",
                                background: "rgba(30, 41, 59, 0.5)",
                                borderRadius: "6px",
                                border: "1px solid rgba(79, 70, 229, 0.2)"
                              }}
                            >
                              <div style={{ marginBottom: "8px" }}>
                                <div style={{ fontSize: "11px", color: "#94a3b8", marginBottom: "4px" }}>
                                  Case ID
                                </div>
                                <div style={{ fontSize: "12px", color: "#e5e7eb", fontFamily: "monospace" }}>
                                  {reviewCase.id}
                                </div>
                              </div>
                              
                              <div style={{ display: "flex", gap: "12px", marginBottom: "8px", fontSize: "11px" }}>
                                <div>
                                  <span style={{ color: "#94a3b8" }}>Tender Docs: </span>
                                  <span style={{ color: "#e5e7eb" }}>{reviewCase.tender_doc_version_ids.length}</span>
                                </div>
                                <div>
                                  <span style={{ color: "#94a3b8" }}>Bid Docs: </span>
                                  <span style={{ color: "#e5e7eb" }}>{reviewCase.bid_doc_version_ids.length}</span>
                                </div>
                              </div>

                              {/* Runs */}
                              {reviewCase.runs.map((run) => (
                                <div
                                  key={run.id}
                                  style={{
                                    marginTop: "8px",
                                    padding: "8px",
                                    background: "rgba(15, 23, 42, 0.5)",
                                    borderRadius: "4px"
                                  }}
                                >
                                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>Run ID: {run.id.substring(0, 12)}...</span>
                                    <span
                                      style={{
                                        padding: "2px 6px",
                                        borderRadius: "3px",
                                        fontSize: "10px",
                                        fontWeight: "600",
                                        background: run.status === "succeeded" ? "rgba(34, 197, 94, 0.2)" :
                                                   run.status === "failed" ? "rgba(239, 68, 68, 0.2)" :
                                                   "rgba(59, 130, 246, 0.2)",
                                        color: run.status === "succeeded" ? "#86efac" :
                                               run.status === "failed" ? "#fca5a5" :
                                               "#93c5fd"
                                      }}
                                    >
                                      {run.status}
                                    </span>
                                  </div>
                                  
                                  {run.findings_stats && (
                                    <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "4px" }}>
                                      <span>Findings: {run.findings_stats.total}</span>
                                      {Object.entries(run.findings_stats.by_result).map(([result, count]) => (
                                        <span key={result} style={{ marginLeft: "8px" }}>
                                          {result}: <span style={{ color: "#e5e7eb" }}>{count}</span>
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                  
                                  <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "4px" }}>
                                    {new Date(run.created_at).toLocaleString()}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </>
            )}

            {/* 刷新按钮 */}
            {(debugData || jobsData || reviewCasesData) && (
              <button
                onClick={handleRefresh}
                disabled={loading}
                style={{
                  marginTop: "16px",
                  width: "100%",
                  padding: "10px",
                  background: "rgba(79, 70, 229, 0.2)",
                  border: "1px solid rgba(79, 70, 229, 0.3)",
                  borderRadius: "6px",
                  color: "#e5e7eb",
                  cursor: loading ? "not-allowed" : "pointer",
                  fontSize: "13px",
                  opacity: loading ? 0.6 : 1
                }}
              >
                {loading ? "⏳ Loading..." : "🔄 Refresh"}
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default DebugPanel;

