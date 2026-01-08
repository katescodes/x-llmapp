#!/usr/bin/env python3
"""
测试AI并行生成标书功能
"""
import asyncio
import logging
import sys
import time
from typing import Dict, Any

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_parallel_generation():
    """测试并行生成功能"""
    from app.services.db.postgres import _get_pool
    from app.dao.tender_directory_node_dao import TenderDirectoryNodeDAO
    from app.dao.tender_section_dao import TenderSectionDAO
    from app.services.tender_service import TenderService
    from app.services.dao.tender_dao import TenderDAO
    from app.services.llm_orchestrator import LLMOrchestrator
    
    pool = _get_pool()
    dao = TenderDAO(pool)
    llm = LLMOrchestrator()
    service = TenderService(dao, llm)
    
    # 获取第一个项目（用于测试）
    projects = dao.list_projects(limit=1)
    if not projects:
        logger.error("没有找到项目，请先创建一个项目")
        return
    
    project_id = projects[0].get("id")
    project_name = projects[0].get("name", "未知项目")
    
    logger.info(f"测试项目: {project_name} (ID: {project_id})")
    
    # 检查是否有目录节点
    node_dao = TenderDirectoryNodeDAO(pool)
    nodes = node_dao.get_active_nodes(project_id)
    
    if not nodes:
        logger.error(f"项目 {project_id} 没有目录节点，请先生成目录")
        return
    
    logger.info(f"找到 {len(nodes)} 个目录节点")
    
    # 清空现有的section（用于测试）
    logger.info("清空现有章节内容以便测试...")
    section_dao = TenderSectionDAO(pool)
    for node in nodes:
        node_id = node.get("id")
        try:
            section_dao.delete_section(project_id, node_id)
        except:
            pass
    
    # 测试串行生成（基准）
    logger.info("\n" + "="*50)
    logger.info("测试1: 串行生成（最多3个章节）")
    logger.info("="*50)
    
    test_nodes = nodes[:3]  # 只测试前3个节点
    start_time = time.time()
    
    # 手动串行生成
    project_context = await service._build_tender_project_context(project_id)
    
    for i, node in enumerate(test_nodes):
        node_id = node.get("id")
        title = node.get("title", "")
        level = node.get("level", 1)
        
        logger.info(f"[{i+1}/{len(test_nodes)}] 生成: {title}")
        
        content = await service._generate_section_content(
            title=title,
            level=level,
            project_context=project_context,
        )
        
        section_dao.upsert_section(
            project_id=project_id,
            node_id=node_id,
            content_html=content,
            content_md="",
        )
    
    serial_time = time.time() - start_time
    logger.info(f"串行生成耗时: {serial_time:.2f} 秒")
    
    # 清空section
    for node in test_nodes:
        node_id = node.get("id")
        section_dao.delete_section(project_id, node_id)
    
    # 测试并行生成
    logger.info("\n" + "="*50)
    logger.info("测试2: 并行生成（最多3个章节，并发数=3）")
    logger.info("="*50)
    
    start_time = time.time()
    
    result = await service.generate_full_content(
        project_id=project_id,
        max_concurrent=3,
    )
    
    parallel_time = time.time() - start_time
    logger.info(f"并行生成耗时: {parallel_time:.2f} 秒")
    logger.info(f"生成结果: {result}")
    
    # 计算加速比
    if serial_time > 0:
        speedup = serial_time / parallel_time
        logger.info(f"\n加速比: {speedup:.2f}x")
    
    # 验证生成的内容
    logger.info("\n" + "="*50)
    logger.info("验证生成的内容")
    logger.info("="*50)
    
    for node in test_nodes:
        node_id = node.get("id")
        title = node.get("title", "")
        
        section = section_dao.get_section(project_id, node_id)
        if section:
            content = section.get("content_html", "")
            word_count = len(content)
            logger.info(f"✓ {title}: {word_count} 字符")
        else:
            logger.warning(f"✗ {title}: 未找到内容")
    
    logger.info("\n测试完成！")


async def test_declare_parallel():
    """测试申报书并行生成"""
    from app.services.db.postgres import _get_pool
    from app.services.dao.declare_dao import DeclareDAO
    from app.services.declare_service import DeclareService
    from app.services.llm_orchestrator import LLMOrchestrator
    
    pool = _get_pool()
    dao = DeclareDAO(pool)
    llm = LLMOrchestrator()
    service = DeclareService(dao, llm)
    
    # 获取第一个项目
    projects = dao.list_projects(limit=1)
    if not projects:
        logger.error("没有找到申报书项目")
        return
    
    project_id = projects[0].get("id")
    project_name = projects[0].get("name", "未知项目")
    
    logger.info(f"\n测试申报书项目: {project_name} (ID: {project_id})")
    
    # 检查是否有目录节点
    nodes = dao.get_active_directory_nodes(project_id)
    if not nodes:
        logger.error("没有目录节点")
        return
    
    logger.info(f"找到 {len(nodes)} 个目录节点")
    
    # 测试并行填充
    logger.info("\n" + "="*50)
    logger.info("测试申报书并行填充章节")
    logger.info("="*50)
    
    start_time = time.time()
    
    try:
        service.autofill_sections(
            project_id=project_id,
            model_id=None,
            max_concurrent=3,
        )
        
        elapsed = time.time() - start_time
        logger.info(f"并行填充耗时: {elapsed:.2f} 秒")
        
    except Exception as e:
        logger.error(f"并行填充失败: {e}", exc_info=True)


def main():
    """主函数"""
    import sys
    
    # 检查参数
    if len(sys.argv) > 1 and sys.argv[1] == "declare":
        logger.info("测试申报书并行生成")
        asyncio.run(test_declare_parallel())
    else:
        logger.info("测试标书并行生成")
        asyncio.run(test_parallel_generation())


if __name__ == "__main__":
    main()

