export class ApiError extends Error {
  constructor(status, data) {
    super(`Request failed with ${status}`)
    this.name = "ApiError"
    // status 0 means the request never completed: refused, offline, DNS.
    // Not "denied" - "unanswered". Nothing may conclude anything about the
    // session from it.
    this.status = status
    this.data = data
  }
}
