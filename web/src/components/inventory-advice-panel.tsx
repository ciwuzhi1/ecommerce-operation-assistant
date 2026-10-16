export function InventoryAdvicePanel(_props: { storeId: number; canEdit?: boolean }) {
  return <section className="rounded-md border border-amber-200 bg-amber-50 p-5">
    <h2 className="font-semibold">库存异常 AI 建议：功能即将上线</h2>
    <p className="mt-2 text-sm">本篇可查看真实库存汇总、低库存和库存流水。大模型补货建议暂不生成。</p>
  </section>;
}
