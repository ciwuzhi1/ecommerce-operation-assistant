"""异步执行进程（DesignSpec §3、§4 / PRD FR-57）。

本包承载 Celery 应用与薄任务封装；业务状态转换一律放在 app.services。
四队列隔离：generation / agent / agent.workflow / maintenance。
"""
