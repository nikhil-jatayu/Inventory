"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DashboardSummary } from "@/lib/types";
import { formatQuantity } from "@/lib/utils";

const AXIS_COLOR = "#64748b";
const GRID_COLOR = "#e2e8f0";

const axisProps = {
  tickLine: false,
  axisLine: false,
  tick: { fontSize: 11, fill: AXIS_COLOR },
} as const;

const tooltipProps = {
  contentStyle: {
    borderRadius: 10,
    borderColor: "#e2e8f0",
    fontSize: 12,
  },
  labelStyle: { color: "#0f172a", fontWeight: 600 },
};

function ChartCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      <div className="px-2 py-3 sm:px-3">{children}</div>
    </section>
  );
}

export function DashboardCharts({ report }: { report: DashboardSummary }) {
  const totalRejected = report.unit_rejections.reduce((sum, issue) => sum + issue.quantity, 0);
  const topIssues = report.unit_rejections.slice(0, 8);
  const pareto = topIssues.map((issue, index) => {
    const cumulative = topIssues
      .slice(0, index + 1)
      .reduce((sum, row) => sum + row.quantity, 0);
    return {
      ...issue,
      shortName: issue.name.length > 16 ? `${issue.name.slice(0, 15)}…` : issue.name,
      cumulative_share:
        totalRejected > 0 ? Math.round((cumulative / totalRejected) * 1000) / 10 : 0,
    };
  });

  return (
    <div className="space-y-4">
      <ChartCard
        title="Monthly dispatch plan, net sales and rejections"
        description={`Quantities in ${report.fy}. Net sales use invoice month; rejections use actual rejection month.`}
      >
        <ResponsiveContainer width="100%" height={290}>
          <BarChart data={report.months} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRID_COLOR} />
            <XAxis {...axisProps} dataKey="label" interval="preserveStartEnd" />
            <YAxis
              {...axisProps}
              width={52}
              tickFormatter={(value) => formatQuantity(Number(value))}
            />
            <Tooltip
              {...tooltipProps}
              cursor={{ fill: "rgba(148, 163, 184, 0.12)" }}
              formatter={(value: unknown, name: unknown) => [
                formatQuantity(Number(value)),
                String(name ?? ""),
              ]}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar
              dataKey="planned"
              name="Planned"
              fill="#f59e0b"
              radius={[4, 4, 0, 0]}
              maxBarSize={22}
            />
            <Bar
              dataKey="sales"
              name="Net sales"
              fill="#4f46e5"
              radius={[4, 4, 0, 0]}
              maxBarSize={22}
            />
            <Bar
              dataKey="rejected"
              name="Rejections recorded"
              fill="#e11d48"
              radius={[4, 4, 0, 0]}
              maxBarSize={22}
            />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard
        title="Top units by rejections"
        description={`Rejected quantity by unit in ${report.fy}, with cumulative share.`}
      >
        {pareto.length === 0 ? (
          <div className="flex h-[260px] items-center justify-center text-sm text-slate-500">
            No rejections recorded for this financial year.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={pareto} margin={{ top: 8, right: 4, left: 0, bottom: 24 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRID_COLOR} />
              <XAxis
                {...axisProps}
                dataKey="shortName"
                interval={0}
                angle={-18}
                textAnchor="end"
                height={50}
              />
              <YAxis
                yAxisId="left"
                {...axisProps}
                width={44}
                tickFormatter={(value) => formatQuantity(Number(value))}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                {...axisProps}
                width={40}
                domain={[0, 100]}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip
                {...tooltipProps}
                cursor={{ fill: "rgba(148, 163, 184, 0.12)" }}
                formatter={(value: unknown, name: unknown) => {
                  const label = String(name ?? "");
                  return label === "Cumulative share"
                    ? [`${Number(value).toFixed(1)}%`, label]
                    : [formatQuantity(Number(value)), label];
                }}
              />
              <Bar
                yAxisId="left"
                dataKey="quantity"
                name="Rejected"
                fill="#4f46e5"
                radius={[4, 4, 0, 0]}
                maxBarSize={34}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="cumulative_share"
                name="Cumulative share"
                stroke="#e11d48"
                strokeWidth={2}
                dot={{ r: 2.5, fill: "#e11d48" }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </ChartCard>
    </div>
  );
}
