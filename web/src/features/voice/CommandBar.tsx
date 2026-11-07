import { useState } from "react";
import { useSubmitText } from "../../api/hooks";
import { Status } from "../../components/Status";
import { MicButton } from "./MicButton";

/** One way in: speak or type a question or a what-if; /api/intent routes it. */
export function CommandBar() {
  const [text, setText] = useState("");
  const intent = useSubmitText();
  const send = (t: string) => { setText(t); if (t.trim()) intent.submit(t.trim()); };
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); send(text); }}>
      <input value={text} onChange={(e) => setText(e.target.value)} size={60} placeholder="Ask, or say “What if we irrigate the driest pea fields?”" aria-label="ask or what-if" />
      <button type="submit" disabled={intent.isPending}>Go</button>
      <MicButton onText={send} />
      <Status loading={intent.isPending} error={intent.error} />
    </form>
  );
}
