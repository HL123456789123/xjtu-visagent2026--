import { afterEach, describe, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { createUserApi, getUserListApi, updateUserRoleApi } from '../admin'

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

  it('creates a normal user through the admin users endpoint', async () => {
    const postSpy = vi.spyOn(request, 'post').mockResolvedValue({ code: 201 })
    const payload = {
      username: 'createduser',
      email: 'created@example.com',
      password: 'password123',
    }

    await createUserApi(payload)

    expect(postSpy).toHaveBeenCalledWith('/admin/users', payload)
  })

  it('passes the search keyword to the user list endpoint', async () => {
    const getSpy = vi.spyOn(request, 'get').mockResolvedValue({
      code: 200,
      data: { items: [], total: 0 },
    })

    await getUserListApi({ page: 1, page_size: 20, keyword: 'alice' })

    expect(getSpy).toHaveBeenCalledWith('/admin/users', {
      params: { page: 1, page_size: 20, keyword: 'alice' },
    })
  })
})
