/**
 * /chat — redirect to the main chat interface at /.
 * This keeps both routes functional in case either is linked.
 */
import { redirect } from "next/navigation";

export default function ChatRedirect() {
  redirect("/");
}
