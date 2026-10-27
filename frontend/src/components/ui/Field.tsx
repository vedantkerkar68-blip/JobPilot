import type { ReactNode, ChangeEvent } from 'react';

interface TextInputProps {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  hint?: string;
  disabled?: boolean;
}

export function TextInput({
  label,
  placeholder,
  value,
  onChange,
  hint,
  disabled,
}: TextInputProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-text-secondary">{label}</label>
      <input
        type="text"
        className="field"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        disabled={disabled}
      />
      {hint ? <p className="text-xs text-text-tertiary leading-snug">{hint}</p> : null}
    </div>
  );
}

interface SelectInputProps {
  label: string;
  value: string;
  onChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  hint?: string;
  children: ReactNode;
  disabled?: boolean;
}

export function SelectInput({
  label,
  value,
  onChange,
  hint,
  children,
  disabled,
}: SelectInputProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-text-secondary">{label}</label>
      <select className="field" value={value} onChange={onChange} disabled={disabled}>
        {children}
      </select>
      {hint ? <p className="text-xs text-text-tertiary leading-snug">{hint}</p> : null}
    </div>
  );
}
