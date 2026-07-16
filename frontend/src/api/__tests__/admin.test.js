import { afterEach, describe, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { updateUserRoleApi } from '../admin'

describe('admin api', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('updates a user identity through the dedicated role endpoint', async () => {
    const putSpy = vi.spyOn(request, 'put').mockResolvedValue({
      code: 200,
      message: '用户身份已设置为管理员',
    })

    await updateUserRoleApi(12, { role: 'admin' })

    expect(putSpy).toHaveBeenCalledOnce()
    expect(putSpy).toHaveBeenCalledWith('/admin/users/12/role', { role: 'admin' })
  })
})
