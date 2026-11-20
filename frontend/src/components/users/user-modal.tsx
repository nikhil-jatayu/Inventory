"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import { ROLE_LABELS, type Role, type User } from "@/lib/types";

interface UserModalProps {
  open: boolean;
  user: User | null;
  currentUserId: number;
  onClose: () => void;
  onSaved: (message: string) => void;
}

const ROLES: Role[] = ["ADMIN", "STORE", "QUALITY", "VIEWER"];

export function UserModal({ open, user, currentUserId, onClose, onSaved }: UserModalProps) {
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [username, setUsername] = useState(user?.username ?? "");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>(user?.role ?? "VIEWER");
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const editingSelf = user?.id === currentUserId;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!fullName.trim()) {
      setError("Full name is required.");
      return;
    }
    if (!user && !/^[a-zA-Z0-9._-]{3,50}$/.test(username.trim())) {
      setError("Username must be 3–50 characters: letters, numbers, dot, underscore or dash.");
      return;
    }
    if (!user && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (user && password && password.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }

    setSaving(true);
    try {
      if (user) {
        await api(`/users/${user.id}`, {
          method: "PATCH",
          body: {
            full_name: fullName.trim(),
            role,
            is_active: isActive,
            ...(password ? { password } : {}),
          },
        });
        onSaved(`${fullName.trim()} updated.`);
      } else {
        await api("/users", {
          method: "POST",
          body: {
            username: username.trim().toLowerCase(),
            full_name: fullName.trim(),
            password,
            role,
          },
        });
        onSaved(`${fullName.trim()} added.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the user.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={user ? "Edit user" : "New user"}
      description={user ? "Update access and reset the password if needed." : "Create an account and assign a role."}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="user-form" loading={saving}>
            {user ? "Save changes" : "Create user"}
          </Button>
        </div>
      }
    >
      <form id="user-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}

        <Field label="Full name" htmlFor="user-name" required>
          <Input
            id="user-name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="e.g. Priya Sharma"
            autoFocus
          />
        </Field>

        {!user && (
          <Field
            label="Username"
            htmlFor="user-username"
            hint="Used to sign in. Letters, numbers, dot, underscore or dash."
            required
          >
            <Input
              id="user-username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="e.g. priya"
              autoComplete="off"
            />
          </Field>
        )}

        <Field
          label={user ? "New password" : "Password"}
          htmlFor="user-password"
          hint={user ? "Leave blank to keep the current password." : "At least 8 characters."}
          required={!user}
        >
          <Input
            id="user-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            placeholder={user ? "Optional" : "Minimum 8 characters"}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Role"
            htmlFor="user-role"
            hint={editingSelf ? "You cannot change your own role." : undefined}
          >
            <Select
              id="user-role"
              value={role}
              disabled={editingSelf}
              onChange={(event) => setRole(event.target.value as Role)}
            >
              {ROLES.map((option) => (
                <option key={option} value={option}>
                  {ROLE_LABELS[option]}
                </option>
              ))}
            </Select>
          </Field>

          {user && (
            <Field
              label="Account status"
              htmlFor="user-active"
              hint={editingSelf ? "You cannot deactivate your own account." : undefined}
            >
              <Select
                id="user-active"
                value={isActive ? "active" : "inactive"}
                disabled={editingSelf}
                onChange={(event) => setIsActive(event.target.value === "active")}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </Select>
            </Field>
          )}
        </div>

        <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-xs text-slate-500">
          <p className="font-medium text-slate-600">Role access</p>
          <p className="mt-1">
            Admin manages users and all data. Store handles items, stock and dispatch. Quality records
            customer rejections. Viewer has read-only dashboard access.
          </p>
        </div>
      </form>
    </Modal>
  );
}
