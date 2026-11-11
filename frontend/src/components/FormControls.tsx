import type { InputHTMLAttributes, ReactNode } from 'react';
export function FormField({label,children,hint}:{label:string;children:ReactNode;hint?:string}) {
  return <label className="field">{label}{children}{hint&&<small>{hint}</small>}</label>;
}
export function SecurePinInput(props:Omit<InputHTMLAttributes<HTMLInputElement>,'type'|'inputMode'>) {
  return <input {...props} type="password" inputMode="numeric" maxLength={6} pattern="[0-9]{6}" className={`secure-pin-input ${props.className||''}`}/>;
}
export function FormError({message}:{message?:string}) { return message?<p className="error-banner" role="alert">{message}</p>:null; }
export function LoadingButton({busy,children,busyLabel='Saving…',disabled=false}:{busy:boolean;children:ReactNode;busyLabel?:string;disabled?:boolean}) {
  return <button type="submit" disabled={busy||disabled} aria-busy={busy}>{busy?busyLabel:children}</button>;
}
export function ConfirmationFooter({children}:{children:ReactNode}) { return <div className="confirmation-footer">{children}</div>; }
