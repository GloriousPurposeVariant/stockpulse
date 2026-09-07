import { ApiError } from "./errors.js"
import { getAccessToken, refresh } from "./tokens.js"

export const api = async (path, options = {}, allowRetry = true) => {
  const token = getAccessToken()

  let response
  try {
    response = await fetch(path, {
      ...options,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    })
  } catch {
    // fetch rejects only when nothing came back at all.
    throw new ApiError(0, null)
  }


  // The access token expired. Get a new one and replay the request once -
  // never twice, or a genuinely signed-out user loops until the stack blows.
  if (response.status === 401 && allowRetry) {
    await refresh()
    return api(path, options, false)
  }

  if (!response.ok) {
    throw new ApiError(response.status, await response.json().catch(() => null))
  }

  return response.status === 204 ? null : response.json()
}
