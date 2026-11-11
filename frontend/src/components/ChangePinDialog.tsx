import {useState} from 'react';
import {Dialog} from './Dialog';
import {FormField,SecurePinInput,FormError,LoadingButton,ConfirmationFooter} from './FormControls';
import {post} from '../lib/api';
export function ChangePinDialog({onClose,onChanged}:{onClose:()=>void;onChanged:()=>void}) {
  const [step,setStep]=useState(0),[values,setValues]=useState(['','','']),[busy,setBusy]=useState(false),[error,setError]=useState(''),[done,setDone]=useState(false);
  const mismatch=step===2&&values[2].length>0&&values[1]!==values[2];
  const close=()=>{setValues(['','','']);onClose();if(done)onChanged();};
  return <Dialog title="Change your wallet PIN" busy={busy} onClose={close}>
    {done?<div role="status"><h3>Your PIN has been updated</h3><p>Unused approvals have been invalidated. Sign in again with your new PIN.</p><button onClick={close}>Done</button></div>:<form className="form-stack" onSubmit={async event=>{
      event.preventDefault();if(busy||values[step].length!==6||mismatch)return;
      if(step<2){setStep(step+1);setError('');return;}
      setBusy(true);setError('');try{await post('/api/security/pin/change',{current_pin:values[0],new_pin:values[1]});setValues(['','','']);setDone(true);}catch(cause){setError((cause as Error).message);}finally{setBusy(false);}
    }}>
      <p role="status">Step {step+1} of 3</p>
      <FormField label={['Current PIN','New PIN','Confirm new PIN'][step]} hint="Six digits. Never share your PIN with the assistant.">
        <SecurePinInput key={step} aria-label={['Current PIN','New PIN','Confirm new PIN'][step]} autoFocus autoComplete={step===0?'current-password':'new-password'} value={values[step]} disabled={busy} onChange={event=>setValues(values.map((v,i)=>i===step?event.target.value.replace(/\D/g,''):v))}/>
      </FormField>
      <p>Changing your PIN invalidates unused approvals, not financial records.</p>
      <FormError message={mismatch?'The new PINs do not match. Go back to edit your new PIN, or enter the same six digits here.':error}/>
      <ConfirmationFooter>{step>0&&<button type="button" className="secondary" disabled={busy} onClick={()=>{setStep(step-1);setError('');}}>Back</button>}<LoadingButton busy={busy} disabled={values[step].length!==6||mismatch} busyLabel="Updating PIN…">{step===2?'Update PIN':'Continue'}</LoadingButton></ConfirmationFooter>
    </form>}
  </Dialog>;
}
