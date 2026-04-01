export function Footer() {
  return (
    <footer className="mt-auto border-t border-slate-200/80 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <div>
          <p className="text-sm font-semibold text-slate-900">VisualCS</p>
          <p className="mt-1 text-xs text-slate-500">
            Interactive CS lessons with diagrams and narration.
          </p>
        </div>
        <p className="text-xs font-medium text-slate-400">
          Powered by Gemini
        </p>
      </div>
    </footer>
  );
}
