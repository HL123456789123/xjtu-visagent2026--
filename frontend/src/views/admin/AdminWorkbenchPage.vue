<template>
  <section class="admin-workbench" data-testid="admin-workbench">
    <header class="admin-workbench__header">
      <div>
        <p>Operations</p>
        <h1>模型工作台</h1>
        <span>集中管理检测、训练、数据、模型与系统权限；普通用户不进入这些运维能力。</span>
      </div>
    </header>

    <section class="admin-workbench__grid" aria-label="模型工作台功能">
      <article v-for="item in visibleItems" :key="item.id" class="workbench-item">
        <el-icon :size="24"><component :is="item.icon" /></el-icon>
        <div>
          <h2>{{ item.title }}</h2>
          <p>{{ item.description }}</p>
        </div>
        <el-button type="primary" text @click="router.push(item.path)">进入</el-button>
      </article>
    </section>

    <el-empty v-if="visibleItems.length === 0" description="当前账号没有可用的运维权限" />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Camera, Cpu, FolderOpened, Goods, Key, UserFilled } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const items = [
  { id: 'detection', title: '传统检测', description: '查看历史检测任务与结果。', path: '/detection', icon: Camera, permission: 'detection:task:view' },
  { id: 'training', title: '模型训练', description: '查看训练任务和当前部署模型状态。', path: '/training', icon: Cpu, permission: 'training:task:view' },
  { id: 'datasets', title: '数据集管理', description: '维护受控的数据集与校验流程。', path: '/datasets', icon: FolderOpened, permission: 'dataset:view' },
  { id: 'models', title: '模型管理', description: '查看版本、部署状态与模型资产。', path: '/models', icon: Goods, permission: 'model:view' },
  { id: 'users', title: '用户管理', description: '管理账号状态与可分配角色。', path: '/admin/users', icon: UserFilled, permission: 'user:list' },
  { id: 'roles', title: '角色管理', description: '维护角色与权限边界。', path: '/admin/roles', icon: Key, permission: 'role:list' },
]

const visibleItems = computed(() => items.filter((item) => userStore.hasPermission(item.permission)))
</script>

<style lang="scss" scoped>
.admin-workbench { max-width: 1120px; margin: 0 auto; }
.admin-workbench__header { margin-bottom: $spacing-lg; }
.admin-workbench__header p { margin: 0 0 6px; color: $primary-color; font-weight: 700; text-transform: uppercase; }
.admin-workbench__header h1 { margin: 0; color: $text-primary; font-size: 28px; }
.admin-workbench__header span { display: block; margin-top: 10px; color: $text-secondary; }
.admin-workbench__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: $spacing-md; }
.workbench-item { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: $spacing-md; padding: $spacing-lg; border: 1px solid #e8edf4; border-radius: 8px; background: #fff; }
.workbench-item > .el-icon { color: $primary-color; }
.workbench-item h2 { margin: 0; color: $text-primary; font-size: 17px; }
.workbench-item p { margin: 6px 0 0; color: $text-secondary; font-size: 14px; line-height: 1.55; }
</style>
