import { Boxes, Plus } from "lucide-react";

import type { ProductSku } from "@/types";

/** 渲染 SkuCreateForm 组件，集中展示SKU创建表单所需的数据、状态和操作入口。 */
export function SkuCreateForm({ canEdit = true, productId }: { canEdit?: boolean; productId: number }) {
  if (!canEdit) {
    // SKU 创建会同步初始化库存档案，只读账号不展示入口，避免误导用户以为可写。
    return (
      <div>
        <h2 className="text-lg font-semibold text-slate-950">鏂板缓 SKU</h2>
        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          当前账号为只读权限，不能新建 SKU。
        </p>
      </div>
    );
  }

  return (
    <form action={`/products/${productId}/skus/create`} method="post" className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-cyan-700 text-white">
          <Boxes className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-slate-950">新建 SKU</h2>
          <p className="text-sm text-slate-500">补齐规格、库存和预警线</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">SKU 编码</span>
          <input
            name="sku_code"
            required
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
            placeholder="例如：SKU-001"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">规格名称</span>
          <input
            name="name"
            required
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
            placeholder="例如：12 包装"
          />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">售价</span>
          <input
            name="price"
            inputMode="decimal"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
            placeholder="29.90"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">成本</span>
          <input
            name="cost"
            inputMode="decimal"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
            placeholder="12.50"
          />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">初始库存</span>
          <input
            name="initial_quantity"
            inputMode="numeric"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
            placeholder="100"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">预警线</span>
          <input
            name="warning_threshold"
            inputMode="numeric"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
            placeholder="20"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">仓位</span>
          <input
            name="location"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
            placeholder="A-01"
          />
        </label>
      </div>

      <button
        type="submit"
        className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
        创建 SKU
      </button>
    </form>
  );
}

/** 渲染 InventoryMovementForm 组件，集中展示库存流水表单所需的数据、状态和操作入口。 */
export function InventoryMovementForm({ productId, sku }: { productId: number; sku: ProductSku }) {
  return (
    <form
      action={`/products/${productId}/skus/${sku.id}/inventory-movements/create`}
      method="post"
      className="grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-[120px_90px_1fr_96px]"
    >
      {/* 表单只收“动作类型 + 数量”，正负 delta 的转换放在服务端 route，保证库存口径统一。 */}
      <label className="block">
        <span className="sr-only">类型</span>
        <select
          name="movement_type"
          defaultValue="inbound"
          className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
        >
          <option value="inbound">入库</option>
          <option value="outbound">出库</option>
          <option value="lock">锁定</option>
          <option value="release">释放</option>
        </select>
      </label>
      <label className="block">
        <span className="sr-only">数量</span>
        <input
          name="quantity"
          required
          inputMode="numeric"
          className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          placeholder="数量"
        />
      </label>
      <label className="block">
        <span className="sr-only">原因</span>
        <input
          name="reason"
          className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          placeholder="原因"
        />
      </label>
      <button
        type="submit"
        className="inline-flex h-9 items-center justify-center rounded-md bg-slate-950 px-3 text-xs font-semibold text-white transition hover:bg-slate-800"
      >
        登记
      </button>
    </form>
  );
}

/** 渲染 SkuInventoryPanel 组件，集中展示SKU库存面板所需的数据、状态和操作入口。 */
export function SkuInventoryPanel({
  productId,
  skus,
  skuStatus,
  inventoryStatus,
  canEdit = true,
}: {
  productId: number;
  skus: ProductSku[];
  skuStatus?: string;
  inventoryStatus?: string;
  canEdit?: boolean;
}) {
  const safeSkus = skus ?? [];

  return (
    <div className="rounded-md border border-slate-200 bg-white p-6">
      {/* 库存面板同时展示当前快照和最近流水，帮助运营判断低库存、锁定占用和盘点差异。 */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">SKU 与库存</h2>
          <p className="mt-1 text-sm text-slate-500">库存变化通过流水登记，便于后续对账和追踪</p>
        </div>
        <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          {safeSkus.length} 个 SKU
        </span>
      </div>

      {skuStatus === "created" ? (
        <p className="mt-3 text-xs font-medium text-emerald-700">SKU 已创建。</p>
      ) : null}
      {skuStatus === "updated" ? (
        <p className="mt-3 text-xs font-medium text-emerald-700">SKU 已更新。</p>
      ) : null}
      {skuStatus === "failed" || inventoryStatus === "failed" ? (
        <p className="mt-3 text-xs font-medium text-rose-700">库存操作失败，请检查数量和权限。</p>
      ) : null}
      {inventoryStatus === "updated" ? (
        <p className="mt-3 text-xs font-medium text-emerald-700">库存流水已登记。</p>
      ) : null}
      {inventoryStatus === "stocktaken" ? (
        <p className="mt-3 text-xs font-medium text-emerald-700">库存盘点已登记。</p>
      ) : null}

      <div className="mt-5 overflow-hidden rounded-md border border-slate-200">
        <div className="hidden grid-cols-[1.1fr_0.8fr_0.7fr_0.7fr_0.7fr] bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500 lg:grid">
          <span>SKU</span>
          <span>价格</span>
          <span>现货</span>
          <span>锁定</span>
          <span>预警</span>
        </div>
        {safeSkus.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-500">还没有 SKU，先在左侧创建一个规格。</div>
        ) : (
          <div className="divide-y divide-slate-200">
            {safeSkus.map((sku) => (
              <div key={sku.id} className="px-4 py-4">
                <div className="grid gap-3 text-sm lg:grid-cols-[1.1fr_0.8fr_0.7fr_0.7fr_0.7fr] lg:items-center">
                  <div>
                    <p className="font-medium text-slate-950">{sku.name}</p>
                    <p className="mt-1 text-xs text-slate-500">{sku.sku_code}</p>
                  </div>
                  <span className="text-slate-600">{sku.price ? `¥${sku.price}` : "-"}</span>
                  <span className="font-medium text-slate-800">{sku.inventory_item?.quantity ?? 0}</span>
                  <span className="text-slate-600">{sku.inventory_item?.locked_quantity ?? 0}</span>
                  <span className="text-slate-600">{sku.inventory_item?.warning_threshold ?? 0}</span>
                </div>
                {canEdit ? (
                  <>
                    <InventoryMovementForm productId={productId} sku={sku} />
                    <details className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2">
                      <summary className="cursor-pointer text-xs font-medium text-slate-700">编辑 SKU / 盘点</summary>
                      <div className="mt-3 grid gap-3 xl:grid-cols-2">
                        <SkuUpdateForm productId={productId} sku={sku} />
                        <StocktakeForm productId={productId} sku={sku} />
                      </div>
                    </details>
                  </>
                ) : null}
                <div className="mt-3 grid gap-2">
                  {(sku.inventory_movements ?? []).slice(0, 3).map((movement) => (
                    <div
                      key={movement.id}
                      className="grid gap-2 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:grid-cols-[90px_90px_90px_1fr]"
                    >
                      <span className="font-medium text-slate-800">{movementTypeLabel(movement.movement_type)}</span>
                      <span>现货 {formatSigned(movement.quantity_delta)}</span>
                      <span>锁定 {formatSigned(movement.locked_delta)}</span>
                      <span className="truncate">{movement.reason ?? movement.created_at}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** 渲染 SkuUpdateForm 组件，集中展示SKU更新表单所需的数据、状态和操作入口。 */
function SkuUpdateForm({ productId, sku }: { productId: number; sku: ProductSku }) {
  return (
    <form action={`/products/${productId}/skus/${sku.id}/update`} method="post" className="grid gap-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-medium text-slate-700">SKU 编码</span>
          <input
            name="sku_code"
            required
            defaultValue={sku.sku_code}
            className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-700">规格名称</span>
          <input
            name="name"
            required
            defaultValue={sku.name}
            className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          />
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="text-xs font-medium text-slate-700">售价</span>
          <input
            name="price"
            inputMode="decimal"
            defaultValue={sku.price ?? ""}
            className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-700">成本</span>
          <input
            name="cost"
            inputMode="decimal"
            defaultValue={sku.cost ?? ""}
            className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-700">状态</span>
          <select
            name="status"
            defaultValue={sku.status}
            className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          >
            <option value="active">启用</option>
            <option value="inactive">停用</option>
          </select>
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-medium text-slate-700">预警线</span>
          <input
            name="warning_threshold"
            inputMode="numeric"
            defaultValue={sku.inventory_item?.warning_threshold ?? 0}
            className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-700">仓位</span>
          <input
            name="location"
            defaultValue={sku.inventory_item?.location ?? ""}
            className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          />
        </label>
      </div>
      <button
        type="submit"
        className="inline-flex h-9 w-fit items-center rounded-md bg-slate-950 px-3 text-xs font-semibold text-white transition hover:bg-slate-800"
      >
        保存 SKU
      </button>
    </form>
  );
}

/** 渲染 StocktakeForm 组件，集中展示盘点表单所需的数据、状态和操作入口。 */
function StocktakeForm({ productId, sku }: { productId: number; sku: ProductSku }) {
  const currentQuantity = sku.inventory_item?.quantity ?? 0;

  return (
    <form action={`/products/${productId}/skus/${sku.id}/inventory-movements/stocktake`} method="post" className="grid gap-3">
      {/* 盘点提交目标库存，服务端根据当前库存计算 adjustment delta，保留盘点流水。 */}
      <input type="hidden" name="current_quantity" value={currentQuantity} />
      <label className="block">
        <span className="text-xs font-medium text-slate-700">盘点后现货</span>
        <input
          name="target_quantity"
          required
          inputMode="numeric"
          defaultValue={currentQuantity}
          className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
        />
      </label>
      <label className="block">
        <span className="text-xs font-medium text-slate-700">盘点说明</span>
        <input
          name="reason"
          className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
          placeholder="例如：月末盘点"
        />
      </label>
      <button
        type="submit"
        className="inline-flex h-9 w-fit items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
      >
        登记盘点
      </button>
    </form>
  );
}

/** 把流水type状态映射为中文显示文本，保持页面口径一致。 */
function movementTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    inbound: "入库",
    outbound: "出库",
    adjustment: "盘点",
    lock: "锁定",
    release: "释放",
  };
  return labels[type] ?? type;
}

/** 格式化带符号，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatSigned(value: number): string {
  if (value > 0) {
    return `+${value}`;
  }
  return String(value);
}
