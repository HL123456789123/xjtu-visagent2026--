import { afterEach, describe, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { getFoodDashboardStatsApi } from '../dashboard'

describe('food dashboard api', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses the Food-specific dashboard endpoint', async () => {
    const getSpy = vi.spyOn(request, 'get').mockResolvedValue({
      code: 200,
      data: { overview: { recognitions: 0 } },
    })

    await getFoodDashboardStatsApi()

    expect(getSpy).toHaveBeenCalledWith('/dashboard/food-stats')
  })
})
