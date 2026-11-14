import { useState } from 'react';
import {
  Check,
  Database,
  Key,
  LogIn,
  LogOut,
  MessageSquare,
  Pencil,
  Plus,
  Shield,
  Sparkles,
  Trash2,
  User,
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
  user,
  guestCount = 0,
  onOpenAuth,
  onOpenAdmin,
  onLogout,
}) {
  const [editingId, setEditingId] = useState(null);
  const [draftTitle, setDraftTitle] = useState('');

  const dbConnected = health?.database === 'connected';
  const aiReady = health?.ai?.ready === true;
  const isAdmin = user?.role === 'ROLE_ADMIN';

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
        className={`fixed top-0 bottom-0 left-0 z-30 flex w-72 flex-col border-r border-white/[0.08] bg-[#0c0d12] transition-transform duration-200 ease-out md:static md:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-4 pt-4 pb-3">
          <div className="flex items-center gap-2.5">
            <ZunoLogo size={24} />
            <span className="text-base font-semibold tracking-tight text-white">
              ZERO
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-white/[0.06] hover:text-white md:hidden"
            title="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={onNewChat}
            className="group flex w-full items-center justify-between rounded-xl border border-white/[0.08] bg-white/[0.04] px-3.5 py-2 text-xs font-medium text-zinc-200 transition hover:border-white/20 hover:bg-white/[0.08]"
          >
            <span className="flex items-center gap-2">
              <Plus className="h-3.5 w-3.5 text-amber-400 transition group-hover:rotate-90" />
              New Chat
            </span>
            <span className="text-[10px] text-zinc-500">Ctrl+K</span>
          </button>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto px-2 py-1">
          <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wider text-zinc-500">
            {user ? 'Private History' : 'Conversations'}
          </div>
          {conversations.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-zinc-500">
              No conversations yet
            </div>
          ) : (
            <ul className="space-y-0.5">
              {conversations.map((conv) => {
                const isActive = conv.id === activeId;
                const isEditing = editingId === conv.id;

                return (
                  <li key={conv.id}>
                    <div
                      onClick={() => !isEditing && onSelect(conv.id)}
                      className={`group flex items-center justify-between rounded-lg px-2.5 py-2 text-xs transition cursor-pointer ${
                        isActive
                          ? 'bg-white/[0.09] text-white font-medium'
                          : 'text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200'
                      }`}
                    >
                      {isEditing ? (
                        <div
                          className="flex flex-1 items-center gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="text"
                            value={draftTitle}
                            onChange={(e) => setDraftTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') commitEdit(conv.id, e);
                              if (e.key === 'Escape') setEditingId(null);
                            }}
                            autoFocus
                            className="flex-1 rounded border border-white/20 bg-black/60 px-1.5 py-0.5 text-xs text-white focus:outline-none"
                          />
                          <button
                            type="button"
                            onClick={(e) => commitEdit(conv.id, e)}
                            className="rounded p-1 text-emerald-400 hover:bg-white/[0.08]"
                          >
                            <Check className="h-3 w-3" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingId(null)}
                            className="rounded p-1 text-zinc-400 hover:bg-white/[0.08]"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <span className="flex flex-1 items-center gap-2 truncate">
                            <MessageSquare className="h-3.5 w-3.5 shrink-0 text-zinc-500" />
                            <span className="truncate">{conv.title}</span>
                          </span>

                          <div className="flex items-center gap-0.5 opacity-0 transition group-hover:opacity-100">
                            <button
                              type="button"
                              onClick={(e) => startEdit(conv, e)}
                              className="rounded p-1 text-zinc-400 hover:bg-white/[0.08] hover:text-white"
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

        {/* User Profile & Auth Section */}
        <div className="border-t border-white/[0.08] bg-[#090a0e] px-3.5 py-3 text-xs">
          {user ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-tr from-amber-500 to-amber-400 text-xs font-bold text-black shadow-sm">
                    {user.name ? user.name[0].toUpperCase() : 'U'}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-semibold text-white text-xs">{user.name}</div>
                    <div className="truncate text-[10px] text-zinc-500">{user.email}</div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={onLogout}
                  className="rounded p-1 text-zinc-500 transition hover:bg-white/[0.08] hover:text-rose-400"
                  title="Sign out"
                >
                  <LogOut className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Token Usage & Role Pill */}
              <div className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-1.5 text-[11px]">
                <span className="flex items-center gap-1.5 text-zinc-400">
                  <Sparkles className="h-3 w-3 text-amber-400" />
                  Tokens:
                </span>
                <span className="font-mono font-medium text-amber-300">
                  {Number(user.totalTokensUsed || 0).toLocaleString()}
                </span>
              </div>

              {/* Admin Panel button if role is ROLE_ADMIN */}
              {isAdmin && (
                <button
                  type="button"
                  onClick={onOpenAdmin}
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 py-1.5 text-[11px] font-semibold text-amber-300 transition hover:bg-amber-500/20"
                >
                  <Shield className="h-3 w-3" />
                  Admin Dashboard
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-zinc-400">Guest Quota:</span>
                <span className={`font-semibold ${guestCount >= 5 ? 'text-rose-400' : 'text-amber-300'}`}>
                  {guestCount}/5 questions
                </span>
              </div>

              <button
                type="button"
                onClick={onOpenAuth}
                className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 py-2 text-xs font-semibold uppercase tracking-wider text-black transition hover:opacity-90"
              >
                <LogIn className="h-3.5 w-3.5" />
                Sign In / Register
              </button>
            </div>
          )}
        </div>

        {/* System Health Indicators */}
        <div className="border-t border-white/[0.07] px-3.5 py-2.5 text-[11px]">
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
          <div className="mt-1 flex items-center justify-between text-zinc-400">
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
