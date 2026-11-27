import { ApiError } from "@/lib/http";

/** Field-level messages from a 422 validation error, keyed by field name. */
export function fieldErrors(e: unknown): Record<string, string> {
  if (!(e instanceof ApiError) || e.code !== "validation_error" || !e.details)
    return {};
  const out: Record<string, string> = {};
  for (const d of e.details) {
    const field = d.field.split(".").pop() ?? d.field;
    if (out[field]) continue;
    if (field === "email")
      out[field] = "Enter a real email address, for example name@gmail.com.";
    else if (field === "password" && /at least/i.test(d.message))
      out[field] = "Use at least 10 characters.";
    else out[field] = d.message;
  }
  return out;
}

/** A plain-language explanation of why signing in or registering failed. */
export function authErrorMessage(
  e: unknown,
  action: "sign-in" | "register",
): string {
  if (!(e instanceof ApiError)) {
    // fetch() itself failed: wrong address, backend down, or blocked by CORS.
    return "Can't reach the ScoutSphere server. Check that the backend is running, then try again.";
  }
  switch (e.code) {
    case "invalid_credentials":
      return "The email or password is incorrect. Passwords are case-sensitive, so check Caps Lock.";
    case "too_many_attempts":
      return e.message; // says how long to wait
    case "account_disabled":
      return "This account has been disabled. Contact your organization's administrator.";
    case "email_taken":
      return "An account with this email already exists.";
    case "validation_error":
      return "Some details need fixing. See the highlighted fields.";
    case "invalid_characters":
      return "Remove any unusual or invisible characters and try again.";
    default:
      if (e.status >= 500)
        return "Something went wrong on our side. Please try again in a moment.";
      return action === "sign-in"
        ? `Couldn't sign you in: ${e.message}`
        : `Couldn't create your account: ${e.message}`;
  }
}
