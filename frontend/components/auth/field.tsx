import type { ComponentProps } from "react";

type Props = ComponentProps<"input"> & { label: string; error?: string };

export function Field({ label, error, id, ...input }: Props) {
  const fieldId = id ?? input.name;
  return (
    <div className="space-y-1">
      <label htmlFor={fieldId} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={fieldId}
        aria-invalid={!!error}
        aria-describedby={error ? `${fieldId}-error` : undefined}
        className="w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 aria-[invalid=true]:border-red-500"
        {...input}
      />
      {error && (
        <p
          id={`${fieldId}-error`}
          role="alert"
          className="text-xs text-red-600"
        >
          {error}
        </p>
      )}
    </div>
  );
}

export function AuthCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center p-6">
      <h1 className="text-2xl font-bold">ScoutSphere</h1>
      <p className="mb-6 text-sm opacity-70">{title}</p>
      {children}
    </main>
  );
}
