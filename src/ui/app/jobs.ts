export async function createJob(baseUrl: string, capability_id: string, input: Record<string, unknown>) {
  const res = await fetch(`${baseUrl}/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ capability_id, input }),
  });
  if (!res.ok) throw new Error(`CREATE_JOB_FAILED:${res.status}`);
  return res.json() as Promise<{ job_id: string }>;
}

export async function getJob(baseUrl: string, jobId: string) {
  const res = await fetch(`${baseUrl}/v1/jobs/${jobId}`);
  if (!res.ok) throw new Error(`JOB_FETCH_FAILED:${res.status}`);
  return res.json();
}

export async function waitJobDone(baseUrl: string, jobId: string, onTick?: (job: any) => void) {
  while (true) {
    const job = await getJob(baseUrl, jobId);
    onTick?.(job);
    if (job.status === "succeeded") return job;
    if (job.status === "failed" || job.status === "canceled") throw new Error(job.error?.message || "JOB_FAILED");
    await new Promise((r) => setTimeout(r, 1200));
  }
}
