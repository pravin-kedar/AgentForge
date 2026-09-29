import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Raw HTML in model output is not rendered (react-markdown's default), so a
// reply can't inject markup or scripts into the page.
const components: Components = {
  table: ({ children }) => (
    <div className="not-prose my-3 overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-left text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-brand-50">{children}</thead>,
  tbody: ({ children }) => <tbody className="divide-y divide-gray-100 bg-white">{children}</tbody>,
  tr: ({ children }) => <tr className="transition-colors hover:bg-gray-50">{children}</tr>,
  th: ({ children }) => (
    <th className="whitespace-nowrap px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-brand-700">
      {children}
    </th>
  ),
  td: ({ children }) => <td className="px-4 py-2.5 align-top text-gray-700">{children}</td>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

export function Markdown({ content }: { content: string }) {
  return (
    <div
      className="prose prose-sm max-w-none prose-headings:mb-2 prose-headings:mt-4 prose-headings:text-gray-900
        prose-h3:text-base prose-p:my-2 prose-p:leading-relaxed prose-a:text-brand-600 prose-strong:text-gray-900
        prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:marker:text-brand-500 prose-hr:my-4
        first:prose-headings:mt-0"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
