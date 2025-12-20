/**
 * 申报书 API Provider
 * 根据环境变量切换 mock/real
 */

// 先导入两个API模块
import * as mockApi from '../mock/declareMockApi';
import * as realApi from './declareApi';

const USE_MOCK = import.meta.env.VITE_DECLARE_USE_MOCK === '1' || import.meta.env.VITE_DECLARE_USE_MOCK === 'true';

// 根据环境变量选择使用哪个API
const selectedApi = USE_MOCK ? mockApi : realApi;

console.log(USE_MOCK ? '[DeclareAPI] Using MOCK API' : '[DeclareAPI] Using REAL API');

// 重新导出所有方法
export const {
  listProjects,
  createProject,
  getProject,
  uploadAssets,
  listAssets,
  extractRequirements,
  getRequirements,
  generateDirectory,
  getDirectoryNodes,
  autofillSections,
  getSections,
  generateDocument,
  exportDocx,
  getRun,
  pollDeclareRun,
  downloadBlob,
} = selectedApi;

// 导出类型
export type {
  DeclareProject,
  DeclareAsset,
  DeclareRun,
  DeclareRequirements,
  DeclareDirectoryNode,
  DeclareSection,
} from './declareApi';

