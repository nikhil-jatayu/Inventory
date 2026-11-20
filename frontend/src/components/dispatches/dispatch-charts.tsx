"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DispatchReport } from "@/lib/types";
import { formatQuantity } from "@/lib/utils";

const AXIS_COLOR = "#64748b";
const GRID_COLOR = "#e2e8f0";

const tooltipProps = {
  contentStyle: {
    borderRadius: 10,
    borderColor: "#e2e8f0",
    fontSize: 12,
  },
  labelStyle: { color: "#0f172a", fontWeight: 600 },
  formatter: (value: unknown) => formatQuantity(Number(value)),
};

const axisProps = {
  tickLine: false,
  axisLine: false,
  tick: { fontSize: 11, fill: AXIS_COLOR },
} as const;

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

export function DispatchCharts({ report }: { report: DispatchReport }) {
  return (
    <div className="space-y-4">
      <ChartCard
        title="Planned vs actual"
        description="Planned and dispatched quantity per month in the selected financial year."
      >
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={report.months} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRID_COLOR} />
            <XAxis
              {...axisProps}
              dataKey="label"
              interval="preserveStartEnd"
            />
            <YAxis
              {...axisProps}
              width={56}
              tickFormatter={(value) => formatQuantity(Number(value))}
            />
            <Tooltip {...tooltipProps} cursor={{ fill: "rgba(148, 163, 184, 0.12)" }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar
              dataKey="planned"
              name="Planned"
              fill="#f59e0b"
              radius={[4, 4, 0, 0]}
              maxBarSize={30}
            />
            <Bar
              dataKey="dispatched"
              name="Dispatched"
              fill="#4f46e5"
              radius={[4, 4, 0, 0]}
              maxBarSize={30}
            />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard
          title="Cumulative dispatch"
          description="Running dispatched quantity from the start of the financial year."
        >
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={report.months} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRID_COLOR} />
              <XAxis {...axisProps} dataKey="label" interval="preserveStartEnd" />
              <YAxis
                {...axisProps}
                width={56}
                tickFormatter={(value) => formatQuantity(Number(value))}
              />
              <Tooltip {...tooltipProps} />
              <Line
                type="monotone"
                dataKey="cumulative"
                name="Cumulative dispatched"
                stroke="#059669"
                strokeWidth={2}
                dot={{ r: 2.5, fill: "#059669" }}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Financial year comparison"
          description="Dispatched and planned quantities by financial year (April–March)."
        >
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={report.fy_totals} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRID_COLOR} />
              <XAxis {...axisProps} dataKey="fy" />
              <YAxis
                {...axisProps}
                width={56}
                tickFormatter={(value) => formatQuantity(Number(value))}
              />
              <Tooltip {...tooltipProps} cursor={{ fill: "rgba(148, 163, 184, 0.12)" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar
                dataKey="planned"
                name="Planned"
                fill="#f59e0b"
                radius={[4, 4, 0, 0]}
                maxBarSize={40}
              />
              <Bar
                dataKey="dispatched"
                name="Dispatched"
                fill="#4f46e5"
                radius={[4, 4, 0, 0]}
                maxBarSize={40}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
