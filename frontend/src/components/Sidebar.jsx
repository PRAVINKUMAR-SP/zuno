import { useState } from 'react';
import {
  Check,
  Database,
  MessageSquare,
  Pencil,
  Plus,
  Trash2,
  X,
} from 'lucide-react';
import ZunoLogo from './ZunoLogo';

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onRename,
  onDelete,
  health,
  isOpen,
  onClose,
}) {
  const [editingId, setEditingId] = useState(null);
  const [draftTitle, setDraftTitle] = useState('');

  const dbConnected = health?.database === 'connected';
  const aiReady = health?.ai?.ready === true;

  const startEdit = (conv, e) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setDraftTitle(conv.title);
  };

  const commitEdit = async (id, e) => {
    e?.stopPropagation();
    const trimmed = draftTitle.trim();
    if (trimmed) {
      await onRename(id, trimmed);
    }
    setEditingId(null);
  };

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-20 bg-black/65 backdrop-blur-xs md:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-68 flex-col border-r border-white/[0.07] bg-[#0f1015] transition-transform duration-200 md:static md:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-4 py-3.5">
          <div className="flex items-center gap-2.5">
            <ZunoLogo size={30} />
            <div className="leading-tight">
              <h1 className="text-sm font-semibold tracking-tight text-zinc-100">Zuno</h1>
              <p className="text-[11px] text-zinc-500">Qwen3-4B Local</p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-100 md:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={onNewChat}
            className="flex w-full items-center justify-between rounded-xl border border-white/[0.09] bg-white/[0.03] px-3 py-2 text-[13px] font-medium text-zinc-200 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
          >
            <span className="flex items-center gap-2">
              <Plus className="h-4 w-4 text-zinc-400" />
              New chat
            </span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2.5 py-2">
          <div className="px-2 pb-1.5 text-[11px] font-medium tracking-wider text-zinc-500 uppercase">
            History
          </div>

          {conversations.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-zinc-600">
              No saved chats yet.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {conversations.map((conv) => {
                const active = conv.id === activeId;
                const isEditing = editingId === conv.id;

                return (
                  <li key={conv.id}>
                    <div
                      onClick={() => !isEditing && onSelect(conv.id)}
                      className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] transition ${
                        active
                          ? 'bg-white/[0.09] font-medium text-white'
                          : 'text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200'
                      }`}
                    >
                      <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />

                      {isEditing ? (
                        <div className="flex flex-1 items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <input
                            value={draftTitle}
                            onChange={(e) => setDraftTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') commitEdit(conv.id, e);
                              if (e.key === 'Escape') setEditingId(null);
                            }}
                            autoFocus
                            className="w-full rounded bg-black/50 px-1.5 py-0.5 text-xs text-white outline-none ring-1 ring-white/30"
                          />
                          <button
                            type="button"
                            onClick={(e) => commitEdit(conv.id, e)}
                            className="rounded p-1 text-emerald-400 hover:bg-white/10"
                          >
                            <Check className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <span className="flex-1 truncate">{conv.title}</span>
                          <div className="hidden items-center gap-0.5 group-hover:flex">
                            <button
                              type="button"
                              onClick={(e) => startEdit(conv, e)}
                              className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-white"
                              title="Rename"
                            >
                              <Pencil className="h-3 w-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onDelete(conv.id);
                              }}
                              className="rounded p-1 text-zinc-400 hover:bg-rose-500/20 hover:text-rose-300"
                              title="Delete"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="border-t border-white/[0.07] px-3.5 py-3 text-[11px]">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="flex items-center gap-2">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  aiReady ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
              />
              Model
            </span>
            <span className={aiReady ? 'text-zinc-300' : 'text-amber-300'}>
              {aiReady ? 'Ready' : 'Offline'}
            </span>
          </div>
          <div className="mt-1.5 flex items-center justify-between text-zinc-400">
            <span className="flex items-center gap-2">
              <Database className="h-3 w-3 text-zinc-500" />
              MySQL
            </span>
            <span className={dbConnected ? 'text-zinc-300' : 'text-rose-400'}>
              {dbConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
