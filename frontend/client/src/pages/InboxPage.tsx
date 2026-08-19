import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Check, ChevronLeft, FileText, Image as ImageIcon, Loader2, MessageCircleMore, Mic, Paperclip, Plus, Search, Send, Users, Volume2, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_BASE_URL, api, readableApiError } from "@/lib/api";

type Attachment = { id: number; attachment_type: "document" | "pdf" | "image" | "voice"; original_filename: string; content_type: string; size_bytes: number; download_url: string; duration_seconds: number | null; created_at: string };
type Member = { id: number; full_name: string; email: string; role: string; joined_at: string; is_active: boolean; last_read_at: string | null };
type Message = { id: number; conversation_id: number; sender_id: number | null; sender_name: string; body: string; attachments: Attachment[]; created_at: string; delivered_at: string | null };
type Conversation = { id: number; conversation_type: "direct" | "group"; title: string; members: Member[]; last_message_at: string | null; last_message_preview: string; unread_count: number; created_at: string };
type Contact = { id: number; full_name: string; email: string; role: string };
type MessagePage = { items: Message[]; next_after_id: number | null };

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "WB";
const formatTime = (value: string | null, language: "sw" | "en") => value ? new Intl.DateTimeFormat(language === "sw" ? "sw-TZ" : "en-GB", { hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "";
const formatSize = (bytes: number) => bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

function attachmentType(file: File): Attachment["attachment_type"] {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("audio/")) return "voice";
  if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) return "pdf";
  return "document";
}

async function openPrivateAttachment(attachment: Attachment, play = false) {
  const response = await fetch(new URL(attachment.download_url, window.location.origin), {
    headers: api.getAccessToken() ? { Authorization: `Bearer ${api.getAccessToken()}` } : {},
    credentials: "include",
  });
  if (!response.ok) throw new Error("Unable to download attachment.");
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  if (play) {
    const audio = new Audio(objectUrl);
    audio.play().catch(() => window.open(objectUrl, "_blank", "noopener,noreferrer"));
    audio.addEventListener("ended", () => URL.revokeObjectURL(objectUrl), { once: true });
    return;
  }
  window.open(objectUrl, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

function AttachmentTile({ attachment, t }: { attachment: Attachment; t: (value: string) => string }) {
  const Icon = attachment.attachment_type === "voice" ? Volume2 : attachment.attachment_type === "image" ? ImageIcon : FileText;
  return <button type="button" onClick={() => void openPrivateAttachment(attachment, attachment.attachment_type === "voice").catch((error) => toast.error(readableApiError(error).message))} className="flex max-w-full items-center gap-2 rounded-xl border border-[#D7E4DF] bg-white/80 px-3 py-2 text-left text-xs font-semibold text-[#28545A] transition hover:border-[#7CB8AE] hover:bg-[#F2FBF8]">
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#DDF0EA] text-[#0F7667]"><Icon size={16} /></span>
    <span className="min-w-0"><span className="block truncate">{attachment.attachment_type === "voice" ? t("Voice message") : attachment.original_filename}</span><span className="mt-0.5 block text-[10px] font-medium text-[#6D817F]">{attachment.duration_seconds ? `${attachment.duration_seconds}s` : formatSize(attachment.size_bytes)}</span></span>
  </button>;
}

function ConversationAvatar({ conversation }: { conversation: Conversation }) {
  return <Avatar className="h-11 w-11 shrink-0 border border-[#D5E4DE] bg-[#E4F0ED]"><AvatarFallback className="bg-[#E4F0ED] text-xs font-extrabold text-[#0E665B]">{conversation.conversation_type === "group" ? <Users size={18} /> : initials(conversation.title)}</AvatarFallback></Avatar>;
}

export default function InboxPage() {
  const { user } = useAuth();
  const { language, t } = useLanguage();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [search, setSearch] = useState("");
  const [body, setBody] = useState("");
  const [loadingInbox, setLoadingInbox] = useState(true);
  const [loadingThread, setLoadingThread] = useState(false);
  const [sending, setSending] = useState(false);
  const [composeOpen, setComposeOpen] = useState(false);
  const [groupMode, setGroupMode] = useState(false);
  const [selectedContacts, setSelectedContacts] = useState<number[]>([]);
  const [groupTitle, setGroupTitle] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const selected = useMemo(() => conversations.find((conversation) => conversation.id === selectedId) ?? null, [conversations, selectedId]);

  const refreshInbox = useCallback(async () => {
    try {
      const result = await api.get<Conversation[]>("/conversations");
      setConversations(result);
      setSelectedId((active) => active && result.some((conversation) => conversation.id === active) ? active : result[0]?.id ?? null);
    } catch (error) {
      toast.error(readableApiError(error).message);
    } finally { setLoadingInbox(false); }
  }, []);

  const loadThread = useCallback(async (conversationId: number, after?: number) => {
    setLoadingThread(!after);
    try {
      const page = await api.get<MessagePage>(`/conversations/${conversationId}/messages${after ? `?after=${after}` : ""}`);
      setMessages((current) => after ? [...current, ...page.items.filter((message) => !current.some((known) => known.id === message.id))] : page.items);
      if (!after) await api.post(`/conversations/${conversationId}/read`);
    } catch (error) { toast.error(readableApiError(error).message); }
    finally { setLoadingThread(false); }
  }, []);

  useEffect(() => { void refreshInbox(); }, [refreshInbox]);
  useEffect(() => { if (selectedId) void loadThread(selectedId); else setMessages([]); }, [selectedId, loadThread]);
  useEffect(() => { const timer = window.setInterval(() => void refreshInbox(), 12_000); return () => window.clearInterval(timer); }, [refreshInbox]);
  useEffect(() => {
    if (!selectedId) return;
    const timer = window.setInterval(() => { const last = messages[messages.length - 1]?.id; void loadThread(selectedId, last); }, 4_500);
    return () => window.clearInterval(timer);
  }, [selectedId, messages, loadThread]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);
  useEffect(() => {
    if (!selectedId || !api.getAccessToken()) return;
    const apiUrl = new URL(API_BASE_URL, window.location.origin);
    const protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${apiUrl.host}/ws/site-management/v1/conversations/${selectedId}/?token=${encodeURIComponent(api.getAccessToken() || "")}`);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { event?: string; message_id?: number };
      if (payload.event === "message.created") {
        const last = messages[messages.length - 1]?.id;
        void loadThread(selectedId, last);
        void refreshInbox();
      }
    };
    return () => socket.close();
  }, [selectedId, messages, loadThread, refreshInbox]);

  const openComposer = async () => {
    setComposeOpen(true); setSelectedContacts([]); setGroupTitle(""); setGroupMode(false);
    try { setContacts(await api.get<Contact[]>("/conversations/contacts")); }
    catch (error) { toast.error(readableApiError(error).message); }
  };
  const createConversation = async () => {
    if ((!groupMode && selectedContacts.length !== 1) || (groupMode && selectedContacts.length < 2)) return;
    setSending(true);
    try {
      const conversation = await api.post<Conversation>("/conversations", { conversation_type: groupMode ? "group" : "direct", title: groupTitle, member_ids: selectedContacts });
      setConversations((current) => [conversation, ...current.filter((item) => item.id !== conversation.id)]);
      setSelectedId(conversation.id); setComposeOpen(false);
    } catch (error) { toast.error(readableApiError(error).message); }
    finally { setSending(false); }
  };
  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId || !body.trim()) return;
    setSending(true);
    try { const message = await api.post<Message>(`/conversations/${selectedId}/messages`, { body }); setMessages((current) => [...current, message]); setBody(""); void refreshInbox(); }
    catch (error) { toast.error(readableApiError(error).message); }
    finally { setSending(false); }
  };
  const sendFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedId) return;
    setSending(true);
    try {
      const data = new FormData(); data.append("file", file); data.append("attachment_type", attachmentType(file));
      const message = await api.request<Message>(`/conversations/${selectedId}/attachments`, { method: "POST", body: data });
      setMessages((current) => [...current, message]); void refreshInbox();
    } catch (error) { toast.error(readableApiError(error).message); }
    finally { setSending(false); event.target.value = ""; }
  };
  const filtered = conversations.filter((conversation) => `${conversation.title} ${conversation.last_message_preview}`.toLowerCase().includes(search.toLowerCase()));

  return <AppShell><div className="mx-auto flex min-h-[calc(100dvh-138px)] max-w-[1480px] flex-col overflow-hidden rounded-[26px] border border-[#D6E1DB] bg-[#FFFEFA] shadow-[0_20px_60px_rgba(27,66,66,.09)] md:grid md:grid-cols-[340px_minmax(0,1fr)]">
    <aside className={`${selected ? "hidden md:flex" : "flex"} min-h-0 min-w-0 flex-col border-r border-[#DCE7E2] bg-[#FAFCF9]`}>
      <div className="border-b border-[#DFE9E5] p-4 sm:p-5"><div className="flex items-center justify-between gap-3"><div><p className="ledger-label text-[#0F7667]">White Bird</p><h2 className="font-serif text-2xl text-[#173A3F]">{t("Messages")}</h2></div><Button onClick={() => void openComposer()} className="h-10 rounded-xl bg-[#0F7667] px-3 text-white hover:bg-[#0B5D53]"><Plus size={18} /><span className="hidden sm:inline">{t("New message")}</span></Button></div><div className="relative mt-4"><Search className="pointer-events-none absolute left-3 top-2.5 text-[#78908C]" size={17} /><Input value={search} onChange={(event) => setSearch(event.target.value)} className="h-10 rounded-xl border-[#D8E6E1] bg-white pl-9" placeholder={t("Search messages")} /></div></div>
      <ScrollArea className="min-h-0 flex-1"><div className="p-2.5">{loadingInbox ? <div className="flex items-center justify-center p-10 text-[#51716D]"><Loader2 className="animate-spin" size={22} /></div> : filtered.length ? filtered.map((conversation) => <button type="button" key={conversation.id} onClick={() => setSelectedId(conversation.id)} className={`flex w-full items-center gap-3 rounded-2xl p-3 text-left transition ${conversation.id === selectedId ? "bg-[#E3F3EE]" : "hover:bg-[#EFF6F3]"}`}><ConversationAvatar conversation={conversation} /><span className="min-w-0 flex-1"><span className="flex items-baseline justify-between gap-2"><strong className="truncate text-sm text-[#193C40]">{conversation.title}</strong><small className="shrink-0 text-[10px] font-semibold text-[#6A817E]">{formatTime(conversation.last_message_at, language)}</small></span><span className="mt-1 flex items-center justify-between gap-2"><span className="truncate text-xs text-[#617975]">{conversation.last_message_preview || t("No messages yet")}</span>{conversation.unread_count > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-[#0F7667] px-1 text-[10px] font-extrabold text-white">{conversation.unread_count > 99 ? "99+" : conversation.unread_count}</span>}</span></span></button>) : <div className="px-5 py-16 text-center"><MessageCircleMore className="mx-auto text-[#A4BBB6]" size={32} /><p className="mt-3 text-sm font-semibold text-[#3F5F5C]">{t("No conversations")}</p><p className="mt-1 text-xs leading-5 text-[#748A86]">{t("Start a secure conversation with an authorised contact.")}</p></div>}</div></ScrollArea>
    </aside>
    <main className={`${selected ? "flex" : "hidden md:flex"} min-h-0 min-w-0 flex-col bg-[#F7FBF9]`}>{selected ? <><div className="flex min-h-[76px] items-center gap-3 border-b border-[#DCE8E2] bg-white/85 px-4 py-3 sm:px-6"><Button variant="ghost" size="icon" onClick={() => setSelectedId(null)} className="md:hidden"><ChevronLeft size={21} /></Button><ConversationAvatar conversation={selected} /><div className="min-w-0 flex-1"><h2 className="truncate font-serif text-xl text-[#163A3E]">{selected.title}</h2><p className="truncate text-xs font-medium text-[#5F7E79]">{selected.conversation_type === "group" ? `${selected.members.length} ${t("members")}` : t("Secure direct conversation")}</p></div><span className="hidden rounded-full bg-[#E5F4EF] px-3 py-1 text-[10px] font-bold uppercase tracking-[.12em] text-[#087363] sm:block">{t("Live")}</span></div>
      <ScrollArea className="min-h-0 flex-1"><div className="mx-auto flex w-full max-w-4xl flex-col gap-3 px-4 py-5 sm:px-7">{loadingThread ? <Loader2 className="mx-auto mt-12 animate-spin text-[#0F7667]" /> : messages.map((message) => { const mine = message.sender_id === user?.id; return <div key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}><div className={`max-w-[88%] rounded-[18px] px-3.5 py-2.5 shadow-sm sm:max-w-[74%] ${mine ? "rounded-br-md bg-[#0F7667] text-white" : "rounded-bl-md border border-[#DDE9E4] bg-white text-[#20464A]"}`}><p className={`mb-1 text-[10px] font-bold ${mine ? "text-[#CDEFE8]" : "text-[#168577]"}`}>{mine ? t("You") : message.sender_name}</p>{message.body && <p className="whitespace-pre-wrap break-words text-sm leading-5">{message.body}</p>}{message.attachments.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{message.attachments.map((attachment) => <AttachmentTile key={attachment.id} attachment={attachment} t={t} />)}</div>}<p className={`mt-1.5 flex items-center justify-end gap-1 text-[10px] ${mine ? "text-[#C8E9E3]" : "text-[#78908D]"}`}>{formatTime(message.created_at, language)}{mine && <Check size={12} />}</p></div></div>})}<div ref={bottom} /></div></ScrollArea>
      <form onSubmit={send} className="border-t border-[#DCE8E2] bg-white p-3 sm:px-5 sm:py-4"><input ref={fileInput} type="file" className="sr-only" accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.jpg,.jpeg,.png,.webp,.mp3,.wav,.m4a,.ogg,.webm" onChange={sendFile} /><div className="flex items-end gap-2"><Button type="button" variant="ghost" size="icon" disabled={sending} onClick={() => fileInput.current?.click()} className="shrink-0 text-[#41726B]"><Paperclip size={20} /><span className="sr-only">{t("Attach file")}</span></Button><Textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder={t("Write a message") } rows={1} className="min-h-11 max-h-32 resize-y rounded-2xl border-[#D7E6E0] bg-[#FBFDFC] py-2.5 text-sm" /><Button type="submit" disabled={sending || !body.trim()} className="h-11 shrink-0 rounded-2xl bg-[#0F7667] px-3.5 text-white hover:bg-[#0B5F55]">{sending ? <Loader2 className="animate-spin" size={18} /> : <Send size={18} />}</Button></div><p className="mt-2 pl-11 text-[10px] text-[#80938F]">{t("Documents, PDFs, images and voice messages stay private and are recorded in the audit trail.")}</p></form>
    </> : <div className="m-auto max-w-sm px-6 text-center"><MessageCircleMore className="mx-auto text-[#A5BBB6]" size={42} /><h2 className="mt-4 font-serif text-2xl text-[#24494C]">{t("Choose a conversation")}</h2><p className="mt-2 text-sm leading-6 text-[#708580]">{t("Select a conversation on the left or start a new secure message.")}</p></div>}</main>
    <Dialog open={composeOpen} onOpenChange={setComposeOpen}><DialogContent className="max-h-[92dvh] w-[calc(100vw-1.25rem)] max-w-lg overflow-y-auto rounded-2xl sm:w-full"><DialogHeader><DialogTitle>{t(groupMode ? "New group" : "New message")}</DialogTitle><DialogDescription>{t("Only authorised contacts are shown for your role.")}</DialogDescription></DialogHeader><div className="flex rounded-xl bg-[#EFF6F3] p-1"><button type="button" onClick={() => { setGroupMode(false); setSelectedContacts([]); }} className={`flex-1 rounded-lg px-3 py-2 text-sm font-bold ${!groupMode ? "bg-white text-[#0F7667] shadow-sm" : "text-[#66817C]"}`}>{t("Direct")}</button><button type="button" onClick={() => { setGroupMode(true); setSelectedContacts([]); }} className={`flex-1 rounded-lg px-3 py-2 text-sm font-bold ${groupMode ? "bg-white text-[#0F7667] shadow-sm" : "text-[#66817C]"}`}>{t("Group")}</button></div>{groupMode && <Input value={groupTitle} onChange={(event) => setGroupTitle(event.target.value)} placeholder={t("Group name")} className="rounded-xl" />}<div className="max-h-72 overflow-y-auto rounded-xl border border-[#DDE9E4] p-1">{contacts.map((contact) => { const checked = selectedContacts.includes(contact.id); return <label key={contact.id} className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-[#F1F8F5]"><Checkbox checked={checked} onCheckedChange={() => setSelectedContacts((current) => checked ? current.filter((id) => id !== contact.id) : groupMode ? [...current, contact.id] : [contact.id])} /><Avatar className="h-8 w-8"><AvatarFallback className="bg-[#E4F0ED] text-[10px] font-bold text-[#0F7667]">{initials(contact.full_name)}</AvatarFallback></Avatar><span className="min-w-0"><strong className="block truncate text-sm text-[#23494B]">{contact.full_name}</strong><span className="block truncate text-xs text-[#78908D]">{t(contact.role.replaceAll("_", " "))}</span></span></label>; })}{!contacts.length && <p className="px-4 py-8 text-center text-sm text-[#6B817D]">{t("No authorised contacts are available right now.")}</p>}</div><DialogFooter><Button variant="outline" onClick={() => setComposeOpen(false)}>{t("Cancel")}</Button><Button disabled={sending || (groupMode ? selectedContacts.length < 2 || !groupTitle.trim() : selectedContacts.length !== 1)} onClick={() => void createConversation()} className="bg-[#0F7667] text-white hover:bg-[#0B5F55]">{sending && <Loader2 className="animate-spin" size={16} />}{t("Start conversation")}</Button></DialogFooter></DialogContent></Dialog>
  </div></AppShell>;
}
