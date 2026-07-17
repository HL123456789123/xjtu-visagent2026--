import { afterEach, describe, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import {
  RECIPE_PATHS,
  createRecipe,
  getRecipe,
  unwrapRecipeApiData,
  createMockRecipeApiClient,
  resetRecipeApiClient,
  setRecipeApiClient,
} from '../recipe'
import { recipeSuccessFixture, recipeV2Fixture } from '@/fixtures/recipe'

describe('recipe api contract', () => {
  afterEach(() => {
    resetRecipeApiClient()
    vi.restoreAllMocks()
  })

  it('keeps the V1 frozen recipe paths', () => {
    expect(RECIPE_PATHS.create).toBe('/recipes')
    expect(RECIPE_PATHS.get(101)).toBe('/recipes/101')
  })

  it('returns cloned success fixture through mock scenario', async () => {
    const result = await createRecipe(
      { recognition_id: 12 },
      { mockScenario: 'success' }
    )

    expect(result.code).toBe(201)
    expect(result.message).toBe('菜谱生成成功')
    expect(result.data.recipe_id).toBe(101)
    expect(result.data.title).toBe('番茄炒蛋')
    expect(result.data.version).toBe(1)
  })

  it('returns v2 fixture through mock scenario', async () => {
    const result = await getRecipe(101, { mockScenario: 'v2' })

    expect(result.code).toBe(200)
    expect(result.data.version).toBe(2)
    expect(result.data.title).toBe('少油版番茄炒蛋')
  })

  it('returns empty fixture through mock scenario', async () => {
    const result = await getRecipe(0, { mockScenario: 'empty' })

    expect(result.code).toBe(200)
    expect(result.data.ingredients).toHaveLength(0)
    expect(result.data.steps).toHaveLength(0)
  })

  it('sends only recognition_id and preferences in create request body', async () => {
    const postSpy = vi.spyOn(request, 'post').mockResolvedValue({
      code: 201,
      data: recipeSuccessFixture,
    })

    await createRecipe(
      { recognition_id: 12, preferences: { servings: 3, taste: '清淡' } },
      { mockScenario: 'off' }
    )

    expect(postSpy).toHaveBeenCalledOnce()
    const [path, body] = postSpy.mock.calls[0]

    expect(path).toBe(RECIPE_PATHS.create)
    expect(body).toEqual({
      recognition_id: 12,
      preferences: { servings: 3, taste: '清淡' },
    })
  })

  it('fills default preferences when not provided', async () => {
    const postSpy = vi.spyOn(request, 'post').mockResolvedValue({
      code: 201,
      data: recipeSuccessFixture,
    })

    await createRecipe({ recognition_id: 12 }, { mockScenario: 'off' })

    const [, body] = postSpy.mock.calls[0]
    expect(body.preferences).toEqual({
      servings: 2,
      taste: '清淡',
      max_time_minutes: 30,
      avoid_ingredients: [],
    })
  })

  it('calls GET /recipes/{recipeId} for getRecipe', async () => {
    const getSpy = vi.spyOn(request, 'get').mockResolvedValue({
      code: 200,
      data: recipeSuccessFixture,
    })

    await getRecipe(101, { mockScenario: 'off' })

    expect(getSpy).toHaveBeenCalledOnce()
    expect(getSpy.mock.calls[0][0]).toBe(RECIPE_PATHS.get(101))
  })

  it('rejects with 503 error on LLM_UNAVAILABLE mock', async () => {
    await expect(getRecipe(101, { mockScenario: 503 })).rejects.toMatchObject({
      response: {
        status: 503,
        data: { code: 'LLM_UNAVAILABLE' },
      },
    })
  })

  it('rejects with 404 on RECIPE_NOT_FOUND mock', async () => {
    await expect(getRecipe(999, { mockScenario: 404 })).rejects.toMatchObject({
      response: {
        status: 404,
        data: { code: 'RECIPE_NOT_FOUND' },
      },
    })
  })

  it('allows an injected client before the real backend is connected', async () => {
    const client = {
      create: vi.fn().mockResolvedValue({ code: 201, data: recipeSuccessFixture }),
      get: vi.fn().mockResolvedValue({ code: 200, data: recipeSuccessFixture }),
    }
    setRecipeApiClient(client)

    await createRecipe({ recognition_id: 12 })
    await getRecipe(101)

    expect(client.create).toHaveBeenCalledOnce()
    expect(client.get).toHaveBeenCalledWith(101, {})
  })

  it('provides a reusable mock client for page-level injection', async () => {
    const client = createMockRecipeApiClient('success')

    const created = await client.create()
    const fetched = await client.get(101)

    expect(created.data.recipe_id).toBe(101)
    expect(fetched.data.recipe_id).toBe(101)
  })

  it('mock client returns v2 when scenario is v2', async () => {
    const client = createMockRecipeApiClient('v2')

    const fetched = await client.get(101)
    expect(fetched.data.version).toBe(2)
  })

  it('unwrapRecipeApiData extracts data field', () => {
    expect(unwrapRecipeApiData({ code: 200, data: { title: 'test' } })).toEqual({
      title: 'test',
    })
    expect(unwrapRecipeApiData({ title: 'direct' })).toEqual({ title: 'direct' })
  })

  it('mock fixture is frozen and cloned (not mutated)', async () => {
    const first = await createRecipe({ recognition_id: 12 }, { mockScenario: 'success' })
    first.data.title = 'MUTATED'

    const second = await createRecipe({ recognition_id: 12 }, { mockScenario: 'success' })
    expect(second.data.title).toBe('番茄炒蛋')
  })
})
