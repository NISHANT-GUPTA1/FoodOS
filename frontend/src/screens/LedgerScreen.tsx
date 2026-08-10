import { useQuery } from '@tanstack/react-query'
import { EmptyState, ErrorState, LoadingState } from '../components/StatePanel'
import { fetchLedgerDashboard } from '../api/mockApi'
import { ProvenanceChip } from '../components/batch/DownstreamLots'
import { SectionHeader } from '../components/SectionHeader'

export function LedgerScreen() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['ledger-dashboard'],
    queryFn: fetchLedgerDashboard,
  })

  if (isLoading) {
    return <LoadingState title="Loading ledger" description="Fetching batch life and risk rows for the current cluster." />
  }

  if (isError || !data) {
    return <ErrorState title="Ledger failed to load" description="The batch rows did not return. Nothing was lost. Retry, or check the API is up on port 8000." />
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Ledger"
        title="Batch life and risk"
        description="The ledger keeps one row per batch so the demo can move from aggregate waste to concrete operational choices."
      />

      {data.batches.length === 0 && (
        <EmptyState
          title="No open batches"
          description="Every batch has been consumed or written off. The ledger repopulates at the next goods receipt."
        />
      )}

      <div className="panel overflow-hidden">
        <table className="min-w-full divide-y divide-[#c4c7c8] text-left text-sm">
          <thead className="bg-[#f1edec] text-xs uppercase tracking-[0.24em] text-[#646464]">
            <tr>
              <th className="px-4 py-3">Batch</th>
              <th className="px-4 py-3">SKU</th>
              <th className="px-4 py-3">Qty</th>
              <th className="px-4 py-3">RSL</th>
              <th className="px-4 py-3">Risk</th>
              <th className="px-4 py-3">Value at risk</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#c4c7c8] bg-white">
            {data.batches.map((row) => (
              <tr key={row.batch} className="text-[#1c1b1b]">
                <td className="px-4 py-4 font-medium text-[#1c1b1b]">
                  <span className="block">{row.batch}</span>
                  {/* Renders only for stock that arrived on a tracked
                      consignment. The kitchen is a different node with a
                      different action space, and it still names the crate the
                      way the farm gate did. */}
                  <ProvenanceChip batchCode={row.batchCode ?? null} origin={row.origin} />
                </td>
                <td className="px-4 py-4">{row.sku}</td>
                <td className="px-4 py-4">{row.qtyKg} kg</td>
                <td className="px-4 py-4">
                  <span className={`chip border border-[#c4c7c8] bg-[#f1edec] ${row.rslDays < 1 ? 'text-[#ba1a1a]' : row.rslDays < 3 ? 'text-[#9a6700]' : 'text-[#0f766e]'}`}>
                    {row.rslDays.toFixed(1)} days
                  </span>
                </td>
                <td className="px-4 py-4">{row.riskPercent}%</td>
                <td className="px-4 py-4">₹{row.valueAtRisk}</td>
                <td className="px-4 py-4 text-[#1c1b1b]">{row.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}