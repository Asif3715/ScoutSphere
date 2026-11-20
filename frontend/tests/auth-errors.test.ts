import { expect, it } from "vitest";

import { authErrorMessage, fieldErrors } from "@/lib/auth-errors";
import { ApiError } from "@/lib/http";

it("explains a wrong password without saying which part was wrong", () => {
  const msg = authErrorMessage(
    new ApiError(401, "invalid_credentials", "Invalid email or password"),
    "sign-in",
  );
  expect(msg).toMatch(/email or password is incorrect/i);
  expect(msg).toMatch(/caps lock/i);
});

it("tells the user when the server cannot be reached", () => {
  expect(authErrorMessage(new TypeError("Failed to fetch"), "sign-in")).toMatch(
    /can't reach/i,
  );
});

it("covers disabled accounts, taken emails and server errors", () => {
  expect(
    authErrorMessage(new ApiError(403, "account_disabled", "x"), "sign-in"),
  ).toMatch(/disabled/i);
  expect(
    authErrorMessage(new ApiError(409, "email_taken", "x"), "register"),
  ).toMatch(/already exists/i);
  expect(
    authErrorMessage(new ApiError(500, "internal_error", "x"), "register"),
  ).toMatch(/our side/i);
});

it("maps backend validation details onto form fields in plain words", () => {
  const e = new ApiError(422, "validation_error", "Invalid request", [
    {
      field: "email",
      message: "value is not a valid email address: reserved name",
    },
    { field: "password", message: "String should have at least 10 characters" },
  ]);
  expect(fieldErrors(e)).toEqual({
    email: "Enter a real email address, for example name@gmail.com.",
    password: "Use at least 10 characters.",
  });
  expect(fieldErrors(new ApiError(401, "invalid_credentials", "x"))).toEqual(
    {},
  );
});
