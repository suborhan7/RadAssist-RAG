import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { StatusChip, OwnershipChip, ServiceChip, Tag, type ReportStatus } from "@/components/ui/chip";
import { AgreementBadge, type Agreement } from "@/components/ui/agreement-badge";
import { SimilarityBar } from "@/components/ui/similarity-bar";
import { Skeleton, SkeletonReport } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * /dev/kitchen-sink — the P0 gate's visual half (design_specification.md §13).
 *
 * Every primitive in every state, on one page. This is not a demo: it is how we
 * notice that the `danger` button was never designed, or that the skeleton and
 * the real card have different heights, before those facts reach a screen.
 * Not linked from the app. Excluded from the production build.
 */
export default function KitchenSink() {
  const statuses: ReportStatus[] = ["draft", "review", "edited", "final"];
  const levels: Agreement[] = ["strong", "mixed", "weak"];

  return (
    <main className="min-h-screen bg-paper p-page">
      <header className="mb-6">
        <h1 className="text-display text-ink">Kitchen sink</h1>
        <p className="mt-1 text-body text-ink-2">
          Every primitive, every state. Design system v2.2 · tokens from{" "}
          <code className="font-mono text-data">src/styles/tokens.css</code>
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4">
        {/* ---------------- Buttons ---------------- */}
        <Card>
          <CardHeader title="Button" sub="One primary per view (§6.7)" />
          <CardBody className="space-y-3">
            {(["sm", "md", "lg"] as const).map((size) => (
              <div key={size} className="flex flex-wrap items-center gap-2">
                <Tag>{size}</Tag>
                <Button variant="primary" size={size}>Primary</Button>
                <Button variant="secondary" size={size}>Secondary</Button>
                <Button variant="ghost" size={size}>Ghost</Button>
                <Button variant="danger" size={size}>Danger</Button>
              </div>
            ))}
            <div className="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
              <Tag>state</Tag>
              <Button variant="primary" loading>Generating</Button>
              <Button variant="primary" disabled>Disabled</Button>
              <Button variant="secondary" disabled>Disabled</Button>
            </div>
            <Button variant="primary" block>Block</Button>
          </CardBody>
        </Card>

        {/* ---------------- Status & ownership ---------------- */}
        <Card>
          <CardHeader title="Status & ownership" sub="§10.1 · §9" />
          <CardBody className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {statuses.map((s) => <StatusChip key={s} status={s} />)}
            </div>
            <div className="flex flex-wrap gap-2 border-t border-hairline pt-3">
              <OwnershipChip doctor={null} />
              <OwnershipChip doctor="Dr. K. Rahman" />
              <OwnershipChip doctor="Dr. S. Mosabber" />
            </div>
            {/* The hatch is redundant to the chip — and at .10 it is visible. */}
            <div className="rounded-card border border-hairline">
              <div className="border-b border-hairline p-tight text-sm">Your study · plain surface</div>
              <div className="bg-hatch p-tight text-sm text-ink-2">Another doctor&apos;s study · hatched</div>
            </div>
            <div className="flex gap-2">
              <Tag>CXR · PA</Tag><Tag tone="steel">Shared registry</Tag>
            </div>
          </CardBody>
        </Card>

        {/* ---------------- Agreement ---------------- */}
        <Card>
          <CardHeader title="Evidence agreement" sub="Not a calibrated probability (§10.3)" />
          <CardBody className="space-y-6">
            {levels.map((level, i) => (
              <AgreementBadge
                key={level}
                level={level}
                factors={{
                  agreeing: [4, 3, 1][i], k: 5,
                  topSimilarity: [97.4, 91.2, 84.6][i],
                  meanSimilarity: [94.1, 88.0, 79.3][i],
                  clinicalHistory: i !== 2,
                  labelSpread: [3, 4, 5][i],
                }}
              />
            ))}
          </CardBody>
        </Card>

        <div className="space-y-4">
          {/* ---------------- Similarity ---------------- */}
          <Card>
            <CardHeader title="Similarity" sub="Retrieved evidence is always steel (§P2)" />
            <CardBody className="space-y-2">
              {[97.4, 95.9, 94.2, 92.6, 90.4].map((v, i) => (
                <div key={v} className="flex items-center gap-3">
                  <span className="w-20 font-mono text-data-sm text-steel">CXR-{2117 + i * 7}</span>
                  <SimilarityBar value={v} highlighted={i === 0} className="flex-1" />
                </div>
              ))}
            </CardBody>
          </Card>

          {/* ---------------- Services ---------------- */}
          <Card>
            <CardHeader title="Service health" sub="§8.1 — the demo's failure mode is Ollama being down"
                        action={<span className="font-mono text-data-sm text-ink-3">live</span>} />
            <CardBody className="py-0">
              <ServiceChip name="FastAPI" value="12ms" />
              <ServiceChip name="Ollama" value="llama3:8b" />
              <ServiceChip name="ChromaDB" value="5,412 vec" />
              <ServiceChip name="GPU" value="6.2/16GB" state="degraded" />
              <ServiceChip name="BiomedCLIP" value="offline" state="offline" />
            </CardBody>
          </Card>
        </div>

        {/* ---------------- Skeletons ---------------- */}
        <Card>
          <CardHeader title="Skeleton" sub="Static blocks. No shimmer (§10.9)" />
          <CardBody><SkeletonReport /></CardBody>
        </Card>

        {/* ---------------- Empty ---------------- */}
        <Card>
          <CardHeader title="Empty state" sub="Always contains the action that resolves it (§7)" />
          <CardBody className="p-0">
            <EmptyState
              title="Your workspace is empty"
              body="Register a patient, or find someone already in the hospital registry. Patients other doctors have reported stay out of your workspace until you report on them yourself."
              actions={<>
                <Button variant="primary" size="lg">Register patient</Button>
                <Button variant="secondary" size="lg">Search registry</Button>
              </>}
            />
          </CardBody>
        </Card>

        {/* ---------------- Type & lightbox ---------------- */}
        <Card>
          <CardHeader title="Type scale" sub="§6.3 · 11px floor" />
          <CardBody className="space-y-2">
            <div className="text-display">Display 28/34</div>
            <div className="text-h1">H1 22/28</div>
            <div className="text-h2">H2 18/24</div>
            <div className="text-h3">H3 15/20</div>
            <p className="text-report">Report body 15/26 — the only continuous prose a human signs their name under.</p>
            <p className="font-bn text-report-bn">বাংলা রিপোর্ট ১৫/২৯ — যুক্তাক্ষরের জন্য বেশি লিডিং প্রয়োজন।</p>
            <div className="text-body">Body 14/21</div>
            <div className="text-sm text-ink-2">Small 13/18</div>
            <div className="text-label">Label 12/16</div>
            <div className="text-eyebrow uppercase text-ink-3">Eyebrow 11/14</div>
            <div className="font-mono text-data">RA-2026-000431 · 97.4% · 6.06s</div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Lightbox" sub="The only dark surface in the product (§P1)" />
          <CardBody>
            <div className="grid h-40 place-items-center rounded-card bg-lightbox">
              <span className="font-mono text-data-sm uppercase tracking-[0.04em] text-lightbox-ink-3">
                Chest X-ray · PA · PHI masked
              </span>
            </div>
            <div className="mt-3 flex gap-2">
              <Skeleton className="h-8 w-8" /><Skeleton className="h-8 w-8" /><Skeleton className="h-8 w-24" />
            </div>
          </CardBody>
        </Card>
      </div>
    </main>
  );
}
