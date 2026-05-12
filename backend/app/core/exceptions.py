"""自定义异常 — 统一错误码体系，对齐 API.md §1.3"""

from fastapi import HTTPException


class AppException(HTTPException):
    """业务异常，携带统一错误码"""

    def __init__(self, code: str, message: str, status_code: int = 400, detail: str = ""):
        self.error_code = code
        self.error_message = message
        self.error_detail = detail
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "detail": detail,
            },
        )


# ==================== 知识库错误 E1xxx ====================

class KnowledgeBaseNotFoundException(AppException):
    def __init__(self, kb_id: int):
        super().__init__("E1001", "知识库不存在", 404, f"kb_id={kb_id} 不存在或已被删除")


class KnowledgeBaseNameExistsException(AppException):
    def __init__(self, name: str):
        super().__init__("E1002", "知识库名称已存在", 409, f"名称 '{name}' 已被使用")


class KnowledgeBaseDeleteFailedException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E1003", "知识库删除失败（关联文档未清空）", 400, detail)


# ==================== 文档错误 E2xxx ====================

class DocumentNotFoundException(AppException):
    def __init__(self, doc_id: int):
        super().__init__("E2001", "文档不存在", 404, f"doc_id={doc_id} 不存在或已被删除")


class UnsupportedFileFormatException(AppException):
    def __init__(self, file_type: str):
        super().__init__("E2002", "文件格式不支持", 415, f"不支持 .{file_type} 格式（仅支持 pdf/docx/md/txt）")


class FileSizeExceededException(AppException):
    def __init__(self):
        super().__init__("E2003", "文件大小超限", 400, "上传文件大小不得超过 50MB")


class DocumentParseFailedException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2004", "文档解析失败", 500, detail)


class DocumentIngestFailedException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2005", "文档入库失败", 500, detail)


# ==================== 会话错误 E3xxx ====================

class ConversationNotFoundException(AppException):
    def __init__(self, conv_id: int):
        super().__init__("E3001", "会话不存在", 404, f"conv_id={conv_id} 不存在或已被删除")


class ConversationAccessDeniedException(AppException):
    def __init__(self):
        super().__init__("E3002", "无权访问此会话", 403, "此会话不属于当前用户")


# ==================== 问答错误 E4xxx ====================

class KnowledgeBaseEmptyException(AppException):
    def __init__(self, kb_id: int):
        super().__init__("E4001", "知识库无可用文档", 400, f"kb_id={kb_id} 下没有文档，请先上传文档")


class LLMCallFailedException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E4002", "LLM 调用失败", 502, detail)


class RetrievalServiceException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E4003", "检索服务异常", 500, detail)


class LLMRateLimitExceededException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E4004", "LLM 调用频率超限", 429, detail)


class QuestionEmptyException(AppException):
    def __init__(self):
        super().__init__("E4005", "问题内容为空", 400, "question 字段不能为空")


# ==================== 认证错误 E5xxx ====================

class UsernameExistsException(AppException):
    def __init__(self, username: str):
        super().__init__("E5001", "用户名已存在", 409, f"用户名 '{username}' 已被注册")


class InvalidCredentialsException(AppException):
    def __init__(self):
        super().__init__("E5002", "用户名或密码错误", 401)


class TokenExpiredException(AppException):
    def __init__(self):
        super().__init__("E5003", "Token 已过期", 401)


class InvalidTokenException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E5004", "Token 无效或格式错误", 401, detail)


class PermissionDeniedException(AppException):
    def __init__(self):
        super().__init__("E5005", "无权限执行此操作", 403)


# ==================== 系统错误 E9xxx ====================

class InternalServerException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E9001", "服务器内部错误", 500, detail)


class ServiceUnavailableException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E9002", "服务暂不可用", 503, detail)


class ValidationFailedException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E9003", "请求参数校验失败", 422, detail)


class RateLimitExceededException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E9004", "请求频率超限", 429, detail)
