import React, { useEffect, useMemo, useRef, useState } from "react";

function cx(...parts) {
  return parts.flatMap((part) => Array.isArray(part) ? part : [part]).filter(Boolean).join(" ");
}

function omitLegacyProps(props) {
  const { variant, bg, size, responsive, hover, striped, bordered, fluid, centered, show, onHide, backdrop, keyboard, closeButton, dialogClassName, animation, ...rest } = props;
  return rest;
}

const buttonVariants = {
  primary: "border-transparent bg-blue-600 text-white shadow-sm hover:bg-blue-700 focus:ring-blue-500",
  secondary: "border-transparent bg-slate-600 text-white shadow-sm hover:bg-slate-700 focus:ring-slate-500",
  success: "border-transparent bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 focus:ring-emerald-500",
  danger: "border-transparent bg-rose-600 text-white shadow-sm hover:bg-rose-700 focus:ring-rose-500",
  warning: "border-transparent bg-amber-400 text-slate-950 shadow-sm hover:bg-amber-500 focus:ring-amber-500",
  info: "border-transparent bg-cyan-500 text-white shadow-sm hover:bg-cyan-600 focus:ring-cyan-500",
  light: "border-slate-200 bg-white text-slate-700 shadow-sm hover:bg-slate-50 focus:ring-blue-500",
  dark: "border-transparent bg-slate-900 text-white shadow-sm hover:bg-slate-800 focus:ring-slate-700",
  link: "border-transparent bg-transparent text-blue-700 underline-offset-4 hover:text-blue-800 hover:underline focus:ring-blue-500",
  "outline-primary": "border-blue-600 bg-white text-blue-700 hover:bg-blue-50 focus:ring-blue-500",
  "outline-secondary": "border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:ring-slate-500",
  "outline-success": "border-emerald-600 bg-white text-emerald-700 hover:bg-emerald-50 focus:ring-emerald-500",
  "outline-danger": "border-rose-600 bg-white text-rose-700 hover:bg-rose-50 focus:ring-rose-500",
  "outline-warning": "border-amber-500 bg-white text-amber-700 hover:bg-amber-50 focus:ring-amber-500",
  "outline-info": "border-cyan-500 bg-white text-cyan-700 hover:bg-cyan-50 focus:ring-cyan-500",
  "outline-light": "border-white/60 bg-transparent text-white hover:bg-white/10 focus:ring-white",
  "outline-dark": "border-slate-900 bg-white text-slate-900 hover:bg-slate-100 focus:ring-slate-700",
};

const badgeVariants = {
  primary: "bg-blue-100 text-blue-800 ring-blue-600/20",
  secondary: "bg-slate-100 text-slate-700 ring-slate-600/20",
  success: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  danger: "bg-rose-100 text-rose-800 ring-rose-600/20",
  warning: "bg-amber-100 text-amber-900 ring-amber-600/20",
  info: "bg-cyan-100 text-cyan-800 ring-cyan-600/20",
  light: "bg-white text-slate-700 ring-slate-200",
  dark: "bg-slate-900 text-white ring-slate-900/20",
};

const alertVariants = {
  primary: "border-blue-200 bg-blue-50 text-blue-900",
  secondary: "border-slate-200 bg-slate-50 text-slate-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  danger: "border-rose-200 bg-rose-50 text-rose-900",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  info: "border-cyan-200 bg-cyan-50 text-cyan-900",
  light: "border-slate-200 bg-white text-slate-700",
  dark: "border-slate-700 bg-slate-900 text-white",
};

export function Button({ as: Component = "button", variant = "primary", size, className = "", disabled, children, ...props }) {
  const isButton = Component === "button";
  const sizes = size === "sm" ? "rounded-lg px-3 py-1.5 text-sm" : size === "lg" ? "rounded-xl px-5 py-3 text-base" : "rounded-xl px-4 py-2 text-sm";
  return (
    <Component
      {...props}
      type={isButton ? props.type || "button" : props.type}
      disabled={isButton ? disabled : undefined}
      aria-disabled={!isButton && disabled ? true : undefined}
      className={cx(
        "btn inline-flex items-center justify-center gap-2 border font-semibold leading-5 transition focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:pointer-events-none disabled:opacity-60",
        sizes,
        buttonVariants[variant] || buttonVariants.primary,
        className
      )}
    >
      {children}
    </Component>
  );
}

export function ButtonGroup({ className = "", children, ...props }) {
  return <div {...props} className={cx("inline-flex flex-wrap items-center gap-2", className)}>{children}</div>;
}

export function Badge({ bg, variant, pill, className = "", children, ...props }) {
  const tone = bg || variant || "secondary";
  return (
    <span {...props} className={cx("badge inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ring-inset", badgeVariants[tone] || badgeVariants.secondary, pill ? "rounded-full" : "", className)}>
      {children}
    </span>
  );
}

export function Alert({ variant = "info", className = "", children, ...props }) {
  return <div {...props} className={cx("alert rounded-2xl border px-4 py-3 text-sm", alertVariants[variant] || alertVariants.info, className)}>{children}</div>;
}

function CardRoot({ className = "", children, ...props }) {
  return <div {...props} className={cx("card overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm", className)}>{children}</div>;
}
function CardBody({ className = "", children, ...props }) {
  return <div {...props} className={cx("card-body p-4", className)}>{children}</div>;
}
function CardHeader({ className = "", children, ...props }) {
  return <div {...props} className={cx("card-header border-b border-slate-200 bg-white px-4 py-3 font-semibold", className)}>{children}</div>;
}
function CardFooter({ className = "", children, ...props }) {
  return <div {...props} className={cx("card-footer border-t border-slate-200 bg-slate-50 px-4 py-3", className)}>{children}</div>;
}
function CardTitle({ as: Component = "h3", className = "", children, ...props }) {
  return <Component {...props} className={cx("card-title text-base font-bold text-slate-950", className)}>{children}</Component>;
}
export const Card = Object.assign(CardRoot, { Body: CardBody, Header: CardHeader, Footer: CardFooter, Title: CardTitle });

const spanMap = {
  1: "w-full md:w-1/12", 2: "w-full md:w-2/12", 3: "w-full md:w-3/12", 4: "w-full md:w-4/12", 5: "w-full md:w-5/12", 6: "w-full md:w-6/12",
  7: "w-full md:w-7/12", 8: "w-full md:w-8/12", 9: "w-full md:w-9/12", 10: "w-full md:w-10/12", 11: "w-full md:w-11/12", 12: "w-full md:w-full",
};
const lgSpanMap = {
  1: "lg:w-1/12", 2: "lg:w-2/12", 3: "lg:w-3/12", 4: "lg:w-4/12", 5: "lg:w-5/12", 6: "lg:w-6/12",
  7: "lg:w-7/12", 8: "lg:w-8/12", 9: "lg:w-9/12", 10: "lg:w-10/12", 11: "lg:w-11/12", 12: "lg:w-full",
};
const xlSpanMap = {
  1: "xl:w-1/12", 2: "xl:w-2/12", 3: "xl:w-3/12", 4: "xl:w-4/12", 5: "xl:w-5/12", 6: "xl:w-6/12",
  7: "xl:w-7/12", 8: "xl:w-8/12", 9: "xl:w-9/12", 10: "xl:w-10/12", 11: "xl:w-11/12", 12: "xl:w-full",
};

export function Row({ className = "", children, ...props }) {
  return <div {...props} className={cx("row -mx-2 flex flex-wrap", className)}>{children}</div>;
}

export function Col({ xs, sm, md, lg, xl, className = "", children, ...props }) {
  const base = typeof xs === "number" ? spanMap[xs] : "w-full";
  const mdClass = typeof md === "number" ? spanMap[md] : typeof sm === "number" ? spanMap[sm] : "";
  const lgClass = typeof lg === "number" ? lgSpanMap[lg] : lg === true ? "lg:flex-1" : "";
  const xlClass = typeof xl === "number" ? xlSpanMap[xl] : xl === true ? "xl:flex-1" : "";
  return <div {...props} className={cx("col px-2", base, mdClass, lgClass, xlClass, className)}>{children}</div>;
}

export function Container({ fluid, className = "", children, ...props }) {
  return <div {...props} className={cx(fluid ? "container-fluid w-full px-4" : "container mx-auto w-full max-w-7xl px-4", className)}>{children}</div>;
}

export function Table({ responsive, hover, striped, bordered, className = "", children, ...props }) {
  const table = (
    <table {...props} className={cx("table min-w-full divide-y divide-slate-200 text-left text-sm", hover ? "table-hover" : "", striped ? "table-striped" : "", bordered ? "border border-slate-200" : "", className)}>
      {children}
    </table>
  );
  if (responsive) return <div className="table-responsive w-full overflow-x-auto">{table}</div>;
  return table;
}

function FieldShell({ as: Component = "div", className = "", children, ...props }) {
  return <Component {...props} className={cx("mb-3", className)}>{children}</Component>;
}
function FormLabel({ className = "", children, ...props }) {
  return <label {...props} className={cx("form-label mb-1 block text-sm font-semibold text-slate-700", className)}>{children}</label>;
}
function FormText({ className = "", children, ...props }) {
  return <div {...props} className={cx("form-text mt-1 text-xs text-slate-500", className)}>{children}</div>;
}
function FormControl({ as = "input", className = "", isInvalid, plaintext, ...props }) {
  const Component = as;
  const type = props.type || "text";
  const inputClass = plaintext
    ? "border-transparent bg-transparent px-0 shadow-none"
    : "rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm transition placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100 disabled:text-slate-500";
  return <Component {...props} type={Component === "input" ? type : undefined} className={cx("form-control block w-full", inputClass, isInvalid ? "border-rose-500 focus:border-rose-500 focus:ring-rose-100" : "", className)} />;
}
function FormSelect({ className = "", isInvalid, ...props }) {
  return <select {...props} className={cx("form-select block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100 disabled:text-slate-500", isInvalid ? "border-rose-500 focus:border-rose-500 focus:ring-rose-100" : "", className)} />;
}
function FormCheck({ className = "", label, type = "checkbox", id, checked, onChange, disabled, ...props }) {
  const controlId = id || useMemo(() => `check-${Math.random().toString(36).slice(2)}`, []);
  return (
    <div className={cx("form-check flex items-center gap-2 py-1", type === "switch" ? "form-switch" : "", className)}>
      <input {...props} id={controlId} type={type === "switch" ? "checkbox" : type} checked={checked} onChange={onChange} disabled={disabled} className={cx(type === "switch" ? "h-5 w-9 rounded-full" : "h-4 w-4 rounded", "border-slate-300 text-blue-600 focus:ring-blue-500 disabled:opacity-60")} />
      {label ? <label htmlFor={controlId} className="form-check-label text-sm text-slate-700">{label}</label> : null}
    </div>
  );
}
function FormRoot({ className = "", children, ...props }) {
  return <form {...props} className={cx(className)}>{children}</form>;
}
export const Form = Object.assign(FormRoot, { Group: FieldShell, Label: FormLabel, Text: FormText, Control: FormControl, Select: FormSelect, Check: FormCheck });

export function InputGroup({ className = "", children, ...props }) {
  return <div {...props} className={cx("input-group flex w-full items-stretch", className)}>{children}</div>;
}
InputGroup.Text = function InputGroupText({ className = "", children, ...props }) {
  return <span {...props} className={cx("input-group-text inline-flex items-center rounded-l-xl border border-r-0 border-slate-300 bg-slate-50 px-3 text-sm text-slate-600", className)}>{children}</span>;
};

export function Spinner({ animation, size, className = "", role = "status", ...props }) {
  return <span {...props} role={role} className={cx("spinner-border inline-block animate-spin rounded-full border-2 border-current border-r-transparent align-[-0.125em]", size === "sm" ? "h-4 w-4" : "h-6 w-6", className)} />;
}

function ModalRoot({ show, onHide, children, className = "", dialogClassName = "", size, centered, backdrop, keyboard, ...props }) {
  useEffect(() => {
    if (!show) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape" && keyboard !== false && onHide) onHide(event);
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [show, keyboard, onHide]);
  if (!show) return null;
  const maxWidth = size === "sm" ? "max-w-md" : size === "lg" ? "max-w-4xl" : size === "xl" ? "max-w-6xl" : "max-w-2xl";
  const enhancedChildren = React.Children.map(children, (child) => {
    if (React.isValidElement(child) && child.type === ModalHeader) {
      return React.cloneElement(child, { onHide: child.props.onHide || onHide });
    }
    return child;
  });
  return (
    <div {...omitLegacyProps(props)} className={cx("modal fixed inset-0 z-[1050] flex p-4", centered ? "items-center" : "items-start pt-12", className)} role="dialog" aria-modal="true">
      <button type="button" aria-label="Fechar" className="modal-backdrop fixed inset-0 bg-slate-950/55" onClick={backdrop === "static" ? undefined : onHide} />
      <div className={cx("modal-dialog relative mx-auto w-full", maxWidth, dialogClassName)}>
        <div className="modal-content overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-slate-900/10">{enhancedChildren}</div>
      </div>
    </div>
  );
}
function ModalHeader({ closeButton, onHide, className = "", children, ...props }) {
  const maybeTitle = React.Children.toArray(children).some((child) => React.isValidElement(child) && child.type === ModalTitle);
  return (
    <div {...props} className={cx("modal-header flex items-start justify-between gap-4 border-b border-slate-200 px-4 py-3", className)}>
      <div className="min-w-0 flex-1">{children}</div>
      {closeButton ? <button type="button" className="btn-close rounded-lg p-1 text-2xl leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-900" aria-label="Fechar" onClick={onHide}>×</button> : null}
    </div>
  );
}
function ModalTitle({ className = "", children, ...props }) {
  return <h2 {...props} className={cx("modal-title text-lg font-bold text-slate-950", className)}>{children}</h2>;
}
function ModalBody({ className = "", children, ...props }) {
  return <div {...props} className={cx("modal-body max-h-[calc(100vh-12rem)] overflow-y-auto px-4 py-4", className)}>{children}</div>;
}
function ModalFooter({ className = "", children, ...props }) {
  return <div {...props} className={cx("modal-footer flex flex-wrap justify-end gap-2 border-t border-slate-200 bg-slate-50 px-4 py-3", className)}>{children}</div>;
}
export const Modal = Object.assign(ModalRoot, { Header: ModalHeader, Title: ModalTitle, Body: ModalBody, Footer: ModalFooter });

function ToastRoot({ show = true, onClose, delay, autohide, className = "", children, ...props }) {
  useEffect(() => {
    if (!show || !autohide || !onClose) return undefined;
    const timeout = setTimeout(onClose, delay || 5000);
    return () => clearTimeout(timeout);
  }, [show, autohide, delay, onClose]);
  if (!show) return null;
  return <div {...props} className={cx("toast rounded-2xl bg-white shadow-xl ring-1 ring-slate-900/10", className)}>{children}</div>;
}
function ToastHeader({ closeButton, onClose, className = "", children, ...props }) {
  return <div {...props} className={cx("toast-header flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-2", className)}><div>{children}</div>{closeButton ? <button type="button" className="btn-close text-xl leading-none text-slate-500" onClick={onClose} aria-label="Fechar">×</button> : null}</div>;
}
function ToastBody({ className = "", children, ...props }) {
  return <div {...props} className={cx("toast-body px-4 py-3 text-sm", className)}>{children}</div>;
}
export const Toast = Object.assign(ToastRoot, { Header: ToastHeader, Body: ToastBody });
export function ToastContainer({ position, className = "", children, ...props }) {
  return <div {...props} className={cx("toast-container fixed z-[2000] space-y-3", position?.includes("top") ? "top-4" : "bottom-4", position?.includes("end") ? "right-4" : "left-4", className)}>{children}</div>;
}

function NavbarRoot({ bg, className = "", children, ...props }) {
  return <nav {...props} className={cx("navbar", bg === "white" ? "bg-white" : "", className)}>{children}</nav>;
}
NavbarRoot.Text = function NavbarText({ className = "", children, ...props }) {
  return <span {...props} className={cx("navbar-text", className)}>{children}</span>;
};
export const Navbar = NavbarRoot;

function DropdownRoot({ className = "", children, ...props }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    function handleClick(event) {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);
  const enhanced = React.Children.map(children, (child) => {
    if (!React.isValidElement(child)) return child;
    if (child.type === DropdownToggle) return React.cloneElement(child, { onClick: (event) => { child.props.onClick?.(event); setOpen((current) => !current); } });
    if (child.type === DropdownMenu) return React.cloneElement(child, { show: open, close: () => setOpen(false) });
    return child;
  });
  return <div {...props} ref={ref} className={cx("dropdown relative inline-flex", className)}>{enhanced}</div>;
}
function DropdownToggle({ split, children, variant = "outline-secondary", size = "sm", className = "", ...props }) {
  return <Button {...props} variant={variant} size={size} className={cx(className)}>{children || (split ? "▾" : "Menu")}</Button>;
}
function DropdownMenu({ show, close, className = "", children, ...props }) {
  if (!show) return null;
  const enhanced = React.Children.map(children, (child) => React.isValidElement(child) && child.type === DropdownItem ? React.cloneElement(child, { close }) : child);
  return <div {...props} className={cx("dropdown-menu absolute right-0 top-full z-50 mt-2 min-w-56 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-xl", className)}>{enhanced}</div>;
}
function DropdownItem({ close, className = "", children, onClick, ...props }) {
  return <button {...props} type="button" className={cx("dropdown-item block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50", className)} onClick={(event) => { onClick?.(event); close?.(); }}>{children}</button>;
}
export const Dropdown = Object.assign(DropdownRoot, { Toggle: DropdownToggle, Menu: DropdownMenu, Item: DropdownItem });
