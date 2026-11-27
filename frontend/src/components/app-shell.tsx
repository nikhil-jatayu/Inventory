"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BadgeAlert,
  Boxes,
  CalendarDays,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  PackageCheck,
  MapPin,
  ReceiptText,
  Scale,
  ShieldCheck,
  ShoppingCart,
  Truck,
  Users,
  Warehouse,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { ROLE_LABELS, roleTone } from "@/lib/types";
import { cn, initials } from "@/lib/utils";

const NAV = [
  {
    href: "/dashboard",
    label: "Dashboard",
    description: "KPIs, Gantt & charts",
    icon: LayoutDashboard,
  },
  {
    href: "/stock",
    label: "Stock",
    description: "Availability & ledger",
    icon: Boxes,
  },
  {
    href: "/items",
    label: "Item Master",
    description: "Items & stock levels",
    icon: Package,
  },
  {
    href: "/purchase-orders",
    label: "Purchase Orders",
    description: "PO bookkeeping references",
    icon: ClipboardList,
  },
  {
    href: "/purchases",
    label: "Purchases",
    description: "Received stock entries",
    icon: ShoppingCart,
  },
  {
    href: "/purchase-planning",
    label: "Purchase Planning",
    description: "Planned replenishment",
    icon: CalendarDays,
  },
  {
    href: "/purchase-rejections",
    label: "Purchase Rejections",
    description: "Purchase plan cancellations",
    icon: PackageCheck,
  },
  {
    href: "/planning",
    label: "Dispatch Planning",
    description: "Gantt dispatch timeline",
    icon: CalendarDays,
  },
  {
    href: "/stock-vs-schedule",
    label: "Stock vs Schedule",
    description: "Shortfall & replenishment",
    icon: Scale,
  },
  {
    href: "/dispatches",
    label: "Actual Dispatch",
    description: "Dispatches against plans",
    icon: Truck,
  },
  {
    href: "/sales",
    label: "Sales",
    description: "Generated dispatch invoices",
    icon: ReceiptText,
  },
  {
    href: "/units",
    label: "Units / Locations",
    description: "Manage dispatch destinations",
    icon: MapPin,
  },
  {
    href: "/rejections",
    label: "Unit Rejections",
    description: "Post-dispatch rejections",
    icon: BadgeAlert,
  },
  {
    href: "/reports",
    label: "Reports",
    description: "Preview & export reports",
    icon: ClipboardList,
  },
  {
    href: "/users",
    label: "Users",
    description: "Accounts & roles",
    icon: Users,
    adminOnly: true,
  },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [logoutConfirm, setLogoutConfirm] = useState(false);

  if (!user) return null;

  const links = NAV.filter(
    (item) => !("adminOnly" in item) || user.role === "ADMIN",
  );
  const current = links.find(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
  );

  return (
    <div className="min-h-screen flex flex-col">
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-[1px] lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform duration-200 lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between gap-2 border-b border-slate-100 px-5">
          <Link href="/dashboard" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-indigo-500 text-white shadow-sm">
              <Warehouse className="h-4.5 w-4.5" />
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-tight text-slate-900">
                Inventory
              </span>
              <span className="block text-[11px] text-slate-500">
                Stock &amp; Dispatch
              </span>
            </span>
          </Link>
          <button
            type="button"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 lg:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-4.5 w-4.5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          <p className="px-2 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Workspace
          </p>
          {links.map(({ href, label, description, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  "group flex items-start gap-3 rounded-lg px-2.5 py-2 transition-colors",
                  active
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                )}
              >
                <Icon
                  className={cn(
                    "mt-0.5 h-4.5 w-4.5 shrink-0",
                    active
                      ? "text-indigo-600"
                      : "text-slate-400 group-hover:text-slate-600",
                  )}
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium">{label}</span>
                  <span
                    className={cn(
                      "block text-xs",
                      active ? "text-indigo-500" : "text-slate-400",
                    )}
                  >
                    {description}
                  </span>
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-slate-100 p-3">
          <div className="flex items-center gap-3 rounded-lg bg-slate-50 px-2.5 py-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
              {initials(user.full_name)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-800">
                {user.full_name}
              </p>
              <p className="truncate text-xs text-slate-500">
                {ROLE_LABELS[user.role]}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setLogoutConfirm(true)}
              className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white hover:text-rose-600"
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64 flex-1 flex flex-col">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/85 backdrop-blur">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700 lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>

            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-medium tracking-wider text-slate-400 uppercase">
                {current?.label ?? "Workspace"}
              </p>
              <p className="truncate text-sm font-medium text-slate-700">
                {current?.description ?? "Inventory management"}
              </p>
            </div>

            <div className="hidden items-center gap-2 sm:flex">
              <span className="text-sm text-slate-500">{user.full_name}</span>
              <Badge tone={roleTone(user.role)}>
                <ShieldCheck className="h-3 w-3" />
                {ROLE_LABELS[user.role]}
              </Badge>
            </div>
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600 ring-1 ring-slate-200 sm:hidden">
              {initials(user.full_name)}
            </span>
          </div>
        </header>

        <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>

        <footer className="mt-auto border-t border-slate-200 bg-slate-50 py-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2 px-4 sm:px-6 lg:px-8">
          <span>
            Developed and maintained by{" "}
            <a
              href="https://www.jatayues.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-600 underline hover:text-indigo-500 font-medium"
            >
              JES Electronic Systems Pvt Ltd
            </a>
          </span>
        </footer>
      </div>

      {logoutConfirm && (
        <Modal
          open={logoutConfirm}
          onClose={() => setLogoutConfirm(false)}
          title="Sign out"
          description="Are you sure you want to sign out of Inventory Management System?"
        >
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setLogoutConfirm(false)}
            >
              Cancel
            </Button>
            <Button type="button" variant="danger" onClick={logout}>
              Sign out
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
