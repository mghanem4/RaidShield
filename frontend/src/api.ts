import type {
  Alert,
  CoordinationGraphData,
  Fixture,
  Health,
  OfflineImport,
  Post,
  Replay,
  ThreadEvent,
} from "./types";
const json = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ error: { message: response.statusText } }));
    throw new Error(body.error?.message ?? "Request failed");
  }
  return response.json() as Promise<T>;
};
const auth = (token: string) => ({
  Authorization: `Bearer ${token}`,
  "Content-Type": "application/json",
});
const bearer = (token: string) => ({ Authorization: `Bearer ${token}` });
export const api = {
  health: () => json<Health>("/api/v1/health"),
  posts: () => json<Post[]>("/api/v1/posts"),
  post: (id: string) => json<Post>(`/api/v1/posts/${id}`),
  coordinationGraph: (id: string) =>
    json<CoordinationGraphData>(`/api/v1/posts/${id}/coordination-graph`),
  alerts: () => json<Alert[]>("/api/v1/alerts"),
  alert: (id: string) => json<Alert>(`/api/v1/alerts/${id}`),
  threads: (id: string, token = "") =>
    json<{ threads: ThreadEvent[]; unknown_parent_replies: ThreadEvent[] }>(
      `/api/v1/posts/${id}/threads${token ? "?include_content=true" : ""}`,
      token ? { headers: auth(token) } : undefined,
    ),
  fixtures: () => json<Fixture[]>("/api/v1/fixtures"),
  replay: (fixture: string, token: string, reset = true) =>
    json<Replay>("/api/v1/replay", {
      method: "POST",
      headers: auth(token),
      body: JSON.stringify({ fixture, speed: 0, reset_before_replay: reset }),
    }),
  importOffline: (file: File, token: string, reset = false) => {
    const body = new FormData();
    body.append("file", file);
    return json<OfflineImport>(
      `/api/v1/offline/import?reset_before_import=${reset}`,
      { method: "POST", headers: bearer(token), body },
    );
  },
  resolve: (id: string, token: string, resolution: string) =>
    json<Alert>(`/api/v1/alerts/${id}`, {
      method: "PATCH",
      headers: auth(token),
      body: JSON.stringify({
        status: "resolved",
        resolution,
        reviewer_note: "Reviewed in the local moderator dashboard.",
      }),
    }),
  reviewContent: (
    id: string,
    token: string,
    review: { score: number; category: string; reviewer_note: string },
  ) =>
    json<Alert>(`/api/v1/alerts/${id}/content-review`, {
      method: "POST",
      headers: auth(token),
      body: JSON.stringify(review),
    }),
  export: async (id: string, token: string) => {
    const response = await fetch(`/api/v1/alerts/${id}/export`, {
      method: "POST",
      headers: auth(token),
    });
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  },
  settings: () =>
    json<Record<string, number | boolean>>("/api/v1/settings/detection"),
  saveSettings: (data: Record<string, number | boolean>, token: string) =>
    json<Record<string, number | boolean>>("/api/v1/settings/detection", {
      method: "PUT",
      headers: auth(token),
      body: JSON.stringify(data),
    }),
  deleteData: (token: string) =>
    json<Record<string, number>>(
      "/api/v1/admin/data?confirmation=DELETE%20LOCAL%20RAIDSHIELD%20DATA",
      { method: "DELETE", headers: auth(token) },
    ),
};
