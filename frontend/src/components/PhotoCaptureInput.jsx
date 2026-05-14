import React, { useId } from "react";
import { Button, Form } from "../ui/TailwindPrimitives.jsx";

export const DEFAULT_IMAGE_ACCEPT = "image/png,image/jpeg,image/webp";

function toFiles(fileList) {
  return Array.from(fileList || []).filter(Boolean);
}

export default function PhotoCaptureInput({
  id,
  accept = DEFAULT_IMAGE_ACCEPT,
  multiple = false,
  disabled = false,
  cameraLabel = "Tirar foto",
  galleryLabel,
  summary,
  helpText,
  className = "",
  capture = "environment",
  onFileChange,
  onFilesChange,
}) {
  const generatedId = useId().replace(/:/g, "");
  const baseId = id || `photo-capture-${generatedId}`;
  const cameraInputId = `${baseId}-camera`;
  const galleryInputId = `${baseId}-gallery`;
  const resolvedGalleryLabel = galleryLabel || (multiple ? "Escolher fotos" : "Escolher arquivo");

  function emit(files, source) {
    if (onFilesChange) onFilesChange(files, { source });
    if (onFileChange) onFileChange(files[0] || null, { source });
  }

  function handleInputChange(event, source) {
    const files = toFiles(event.target.files);
    emit(files, source);
    event.target.value = "";
  }

  return (
    <div className={className}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          id={cameraInputId}
          className="sr-only"
          type="file"
          accept={accept}
          capture={capture}
          disabled={disabled}
          onChange={(event) => handleInputChange(event, "camera")}
        />
        <Button as="label" htmlFor={cameraInputId} type="button" variant="outline-success" className="mb-0 w-full sm:w-auto" disabled={disabled}>
          📷 {cameraLabel}
        </Button>

        <input
          id={galleryInputId}
          className="sr-only"
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={disabled}
          onChange={(event) => handleInputChange(event, "gallery")}
        />
        <Button as="label" htmlFor={galleryInputId} type="button" variant="outline-primary" className="mb-0 w-full sm:w-auto" disabled={disabled}>
          {resolvedGalleryLabel}
        </Button>
      </div>

      {summary ? <div className="mt-2 truncate text-xs text-slate-500" title={summary}>{summary}</div> : null}
      {helpText ? <Form.Text>{helpText}</Form.Text> : null}
    </div>
  );
}
