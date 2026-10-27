interface SectionHeadingProps {
  index?: string;
  title: string;
  description?: string;
  meta?: string;
}

export function SectionHeading({ title, description, meta }: SectionHeadingProps) {
  return (
    <div className="mb-2">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-text">{title}</h1>
        {meta ? (
          <span className="text-xs text-text-tertiary shrink-0">{meta}</span>
        ) : null}
      </div>
      {description ? (
        <p className="mt-1 text-sm text-text-secondary max-w-2xl leading-relaxed">
          {description}
        </p>
      ) : null}
    </div>
  );
}
