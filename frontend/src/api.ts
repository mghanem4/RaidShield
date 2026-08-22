import type {
  Alert,
  Fixture,
  Health,
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
export const api = {
  health: () => json<Health>("/api/v1/health"),
  posts: () => json<Post[]>("/api/v1/posts"),
  post: (id: string) => json<Post>(`/api/v1/posts/${id}`),
  alerts: () => json<Alert[]>("/api/v1/alerts"),
  alert: (id: string) => json<Alert>(`/api/v1/alerts/${id}`),
  threads: (id: string) =>
    json<{ threads: ThreadEvent[]; unknown_parent_replies: ThreadEvent[] }>(
      `/api/v1/posts/${id}/threads`,
    ),
  fixtures: () => json<Fixture[]>("/api/v1/fixtures"),
  replay: (fixture: string, token: string, reset = true) =>
    json<Replay>("/api/v1/replay", {
      method: "POST",
      headers: auth(token),
      body: JSON.stringify({ fixture, speed: 0, reset_before_replay: reset }),
    }),
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
