import { useEffect, useState } from 'react';
import { AlertCircle, Check, Edit2, RefreshCw, Shield, Users, X } from 'lucide-react';
import { getAdminUsers, updateUserLimit } from '../api/zunoApi';

export default function AdminDashboardModal({ isOpen, onClose }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editingUserId, setEditingUserId] = useState(null);
  const [newLimit, setNewLimit] = useState('');
  const [updating, setUpdating] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getAdminUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Failed to fetch users. Admin access required.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchUsers();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSaveLimit = async (userId) => {
    setUpdating(true);
    try {
      const parsed = parseInt(newLimit, 10);
      const val = isNaN(parsed) ? -1 : parsed;
      const updated = await updateUserLimit(userId, val);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, tokenLimit: updated.tokenLimit } : u)));
      setEditingUserId(null);
    } catch (err) {
      alert(`Error updating limit: ${err.message}`);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-white/[0.14] bg-[#101117] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1 text-zinc-400 transition hover:bg-white/[0.08] hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="mb-5 flex items-center justify-between border-b border-white/[0.08] pb-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/15 text-amber-400">
              <Shield className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-base font-semibold text-white">ZERO Admin Dashboard</h3>
              <p className="text-xs text-zinc-400">Manage registered users, monitor token usage, and adjust limits</p>
            </div>
          </div>

          <button
            type="button"
            onClick={fetchUsers}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-white/[0.08] disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="max-h-[55vh] overflow-auto rounded-xl border border-white/[0.08] bg-black/30">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="sticky top-0 border-b border-white/[0.08] bg-[#161720] text-[11px] uppercase tracking-wider text-zinc-400">
              <tr>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Tokens Used</th>
                <th className="px-4 py-3">Token Limit</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {users.length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-zinc-500">
                    No users registered yet.
                  </td>
                </tr>
              )}
              {users.map((u) => {
                const isEditing = editingUserId === u.id;
                const isAdmin = u.role === 'ROLE_ADMIN';
                return (
                  <tr key={u.id} className="transition hover:bg-white/[0.02]">
                    <td className="px-4 py-3">
                      <div className="font-medium text-white">{u.name}</div>
                      <div className="text-[11px] text-zinc-500">{u.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] uppercase font-semibold ${
                          isAdmin
                            ? 'border border-amber-500/30 bg-amber-500/15 text-amber-300'
                            : 'border border-sky-500/30 bg-sky-500/15 text-sky-300'
                        }`}
                      >
                        {isAdmin && <Shield className="h-2.5 w-2.5" />}
                        {isAdmin ? 'Admin' : 'User'}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono font-medium text-amber-300">
                      {Number(u.totalTokensUsed || 0).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      {isEditing ? (
                        <input
                          type="number"
                          value={newLimit}
                          onChange={(e) => setNewLimit(e.target.value)}
                          placeholder="-1 for unlimited"
                          className="w-28 rounded border border-amber-400/50 bg-black px-2 py-1 text-xs text-white focus:outline-none"
                        />
                      ) : (
                        <span className="text-zinc-400">
                          {u.tokenLimit === -1 || !u.tokenLimit ? 'Unlimited' : Number(u.tokenLimit).toLocaleString()}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isEditing ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            disabled={updating}
                            onClick={() => handleSaveLimit(u.id)}
                            className="flex items-center gap-1 rounded bg-amber-500 px-2 py-1 text-[11px] font-semibold text-black hover:bg-amber-400"
                          >
                            <Check className="h-3 w-3" /> Save
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingUserId(null)}
                            className="rounded px-2 py-1 text-[11px] text-zinc-400 hover:text-white"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setEditingUserId(u.id);
                            setNewLimit(String(u.tokenLimit ?? -1));
                          }}
                          className="inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] text-zinc-400 transition hover:bg-white/[0.08] hover:text-zinc-200"
                        >
                          <Edit2 className="h-3 w-3" /> Set Limit
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

