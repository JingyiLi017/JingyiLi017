import type { ReactNode, RefObject } from "react";

type DeleteConfirmDialogProps = {
  open: boolean;
  title: string;
  requireInput?: boolean;
  targetLabel?: ReactNode;
  warning: ReactNode;
  expectedText: string;
  value: string;
  promptLabel?: ReactNode;
  placeholder?: string;
  busy?: boolean;
  error?: string;
  inputClassName?: string;
  inputRef?: RefObject<HTMLInputElement>;
  confirmLabel?: string;
  busyLabel?: string;
  onValueChange: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  onMismatch?: () => void;
};

export function DeleteConfirmDialog(props: DeleteConfirmDialogProps) {
  const {
    open,
    title,
    requireInput = false,
    targetLabel,
    warning,
    expectedText,
    value,
    promptLabel,
    placeholder,
    busy = false,
    error = "",
    inputClassName = "",
    inputRef,
    confirmLabel = "确认删除",
    busyLabel = "删除中...",
    onValueChange,
    onConfirm,
    onCancel,
    onMismatch,
  } = props;

  if (!open) return null;

  const expected = String(expectedText || "").trim();
  const typed = String(value || "").trim();
  const canConfirm = !busy && (!requireInput || (!!expected && typed === expected));

  return (
    <div
      className="delete-confirm-overlay"
      onMouseDown={() => {
        if (busy) return;
        onCancel();
      }}
    >
      <div className="delete-confirm-modal" onMouseDown={(e) => e.stopPropagation()}>
        <h4>{title}</h4>
        {targetLabel ? <div className="small">{targetLabel}</div> : null}
        <div className="danger" style={{ marginTop: 8 }}>
          {warning}
        </div>
        {requireInput ? (
          <label style={{ marginTop: 10 }}>
            {promptLabel || "请输入目标名称以确认删除"}
            <input
              ref={inputRef}
              className={inputClassName}
              value={value}
              onChange={(e) => onValueChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  if (busy) return;
                  if (typed === expected) onConfirm();
                  else onMismatch?.();
                } else if (e.key === "Escape" && !busy) {
                  e.preventDefault();
                  onCancel();
                }
              }}
              placeholder={placeholder || expected}
            />
          </label>
        ) : null}
        {error ? (
          <div className="small danger" style={{ marginTop: 8 }}>
            {error}
          </div>
        ) : null}
        <div className="row" style={{ gap: 8, marginTop: 10, justifyContent: "flex-end" }}>
          <button onClick={onCancel} disabled={busy}>
            取消
          </button>
          <button className="danger" onClick={onConfirm} disabled={!canConfirm}>
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
