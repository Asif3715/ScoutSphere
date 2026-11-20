import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/**
 * False in the server-rendered HTML and true once React is running in the browser. Forms use
 * it to keep their submit button disabled until JavaScript can handle the submission, so a
 * fast click can never fall back to a silent full-page form post.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
