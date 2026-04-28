import { describe, it, expect } from 'vitest'
import { updateFeatureInTree, applyGroupFeaturePermissions, applyGroupSwitch } from '@/utils/tree'
import type { FeatureItem, PermissionMatrixGroup } from '@/apis/permission'

function makeFeature(name: string, enabled: boolean, children: FeatureItem[] = []): FeatureItem {
  return {
    name,
    parent: null,
    display_name: name,
    description: '',
    default_enabled: false,
    enabled,
    is_active: true,
    children,
  }
}

function makeGroup(id: number, permissions: Record<string, boolean> = {}): PermissionMatrixGroup {
  return { group_id: id, bot_enabled: true, permissions }
}

describe('updateFeatureInTree', () => {
  it('更新顶级节点 enabled', () => {
    const tree = [makeFeature('a', false), makeFeature('b', true)]
    updateFeatureInTree(tree, 'a', true)
    expect(tree[0].enabled).toBe(true)
    expect(tree[1].enabled).toBe(true)
  })

  it('更新嵌套子节点', () => {
    const child = makeFeature('child', false)
    const tree = [makeFeature('parent', true, [child])]
    updateFeatureInTree(tree, 'child', true)
    expect(tree[0].children[0].enabled).toBe(true)
  })

  it('名称不存在时不抛出错误', () => {
    const tree = [makeFeature('a', false)]
    expect(() => updateFeatureInTree(tree, 'nonexistent', true)).not.toThrow()
  })

  it('空数组时不抛出', () => {
    expect(() => updateFeatureInTree([], 'a', true)).not.toThrow()
  })
})

describe('applyGroupFeaturePermissions', () => {
  it('写入群组权限', () => {
    const groups = [makeGroup(1)]
    applyGroupFeaturePermissions(groups, 1, [{ feature_name: 'echo', enabled: true }])
    expect(groups[0].permissions['echo']).toBe(true)
  })

  it('多条权限批量写入', () => {
    const groups = [makeGroup(2)]
    applyGroupFeaturePermissions(groups, 2, [
      { feature_name: 'f1', enabled: true },
      { feature_name: 'f2', enabled: false },
    ])
    expect(groups[0].permissions['f1']).toBe(true)
    expect(groups[0].permissions['f2']).toBe(false)
  })

  it('groupId 不存在时不抛出', () => {
    const groups = [makeGroup(1)]
    expect(() =>
      applyGroupFeaturePermissions(groups, 999, [{ feature_name: 'f', enabled: true }]),
    ).not.toThrow()
  })
})

describe('applyGroupSwitch', () => {
  it('设置群组 bot_enabled', () => {
    const groups = [makeGroup(1)]
    applyGroupSwitch(groups, 1, false)
    expect(groups[0].bot_enabled).toBe(false)
  })

  it('groupId 不存在时不抛出', () => {
    const groups = [makeGroup(1)]
    expect(() => applyGroupSwitch(groups, 999, false)).not.toThrow()
  })
})
