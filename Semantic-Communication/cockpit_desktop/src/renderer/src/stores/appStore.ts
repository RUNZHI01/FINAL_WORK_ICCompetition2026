import { create } from 'zustand'
import type { RunInferenceResponse } from '../api/types'

export type ComparisonEngineKey = 'pytorch' | 'tvm' | 'mnn'

export type ComparisonResult = {
  engine: ComparisonEngineKey
  label: string
  reconstructionMs: number
  runMs?: number
  sampleCount?: number
  updatedAt?: number
  quality?: {
    psnr_db?: number
    ssim?: number
  }
}

type AppState = {
  appTitle: string
  activeJobId: string | null
  /** Last completed live inference result in the current renderer session. */
  lastCompletedInference: RunInferenceResponse | null
  lastSettledBatchToken: string | null
  pendingBatchJobId: string | null
  comparisonResults: Partial<Record<ComparisonEngineKey, ComparisonResult>>
  chinaTheater: boolean
}

type AppActions = {
  setActiveJobId: (id: string | null) => void
  setLastCompletedInference: (data: RunInferenceResponse | null) => void
  setLastSettledBatchToken: (token: string | null) => void
  setPendingBatchJobId: (id: string | null) => void
  setComparisonResult: (engine: ComparisonEngineKey, result: ComparisonResult) => void
  clearComparisonResults: () => void
  setChinaTheater: (v: boolean) => void
}

export const useAppStore = create<AppState & AppActions>()((set) => ({
  appTitle: '飞腾多核弱网安全语义视觉回传 · 座舱演示',
  activeJobId: null,
  lastCompletedInference: null,
  lastSettledBatchToken: null,
  pendingBatchJobId: null,
  comparisonResults: {},
  chinaTheater: false,
  setActiveJobId: (id) => set({ activeJobId: id }),
  setLastCompletedInference: (data) => set({ lastCompletedInference: data }),
  setLastSettledBatchToken: (token) => set({ lastSettledBatchToken: token }),
  setPendingBatchJobId: (id) => set({ pendingBatchJobId: id }),
  setComparisonResult: (engine, result) => set((state) => ({
    comparisonResults: {
      ...state.comparisonResults,
      [engine]: result,
    },
  })),
  clearComparisonResults: () => set({ comparisonResults: {} }),
  setChinaTheater: (v) => set({ chinaTheater: v }),
}))
