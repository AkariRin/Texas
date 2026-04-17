import client from './client'

export interface PoolInfo {
  id: number
  name: string
  available_count: number
}

export interface PoolGroupsResponse {
  pool_id: number
  group_ids: number[]
}

/** 列出所有漂流瓶池（含未捞取瓶数统计） */
export async function listPools(): Promise<PoolInfo[]> {
  const res = await client.get<{ code: number; data: PoolInfo[] }>('/drift-bottle-pools')
  return res.data.data
}

/** 创建新漂流瓶池 */
export async function createPool(name: string): Promise<{ id: number; name: string }> {
  const res = await client.post<{ code: number; data: { id: number; name: string } }>(
    '/drift-bottle-pools',
    { name },
  )
  return res.data.data
}

/** 删除漂流瓶池（id=0 的默认池后端会拒绝） */
export async function deletePool(poolId: number): Promise<void> {
  await client.post(`/drift-bottle-pools/${poolId}/delete`)
}

/** 列出指定池下所有群号 */
export async function listPoolGroups(poolId: number): Promise<PoolGroupsResponse> {
  const res = await client.get<{ code: number; data: PoolGroupsResponse }>(
    `/drift-bottle-pools/${poolId}/groups`,
  )
  return res.data.data
}

/** 将群分配到指定池（poolId=0 = 移回默认池） */
export async function assignGroupPool(groupId: number, poolId: number): Promise<void> {
  await client.post('/drift-bottle-pools/group-assign', { group_id: groupId, pool_id: poolId })
}
