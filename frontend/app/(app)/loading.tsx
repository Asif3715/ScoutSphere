/** Shown instantly while the next page loads, so the screen reacts the moment you click. */
export default function Loading() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading page">
      <div className="space-y-3 border-b border-line pb-5">
        <span className="skeleton block h-3 w-16" />
        <span className="skeleton block h-10 w-64 max-w-full" />
        <span className="skeleton block h-3.5 w-80 max-w-full" />
      </div>
      <div className="table-card">
        <div className="table-toolbar">
          <span className="skeleton block h-9 w-56 max-w-full" />
          <span className="skeleton block h-9 w-32" />
        </div>
        <div className="space-y-4 p-4">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="skeleton h-9 w-9 shrink-0" />
              <span className="flex-1 space-y-2">
                <span className="skeleton block h-3.5 w-2/5" />
                <span className="skeleton block h-3 w-1/4" />
              </span>
              <span className="skeleton hidden h-4 w-16 sm:block" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
