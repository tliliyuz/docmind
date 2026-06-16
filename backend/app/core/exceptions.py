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


class StorageErrorException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2006", "存储错误", 500, detail)


class VectorStoreErrorException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2007", "向量存储错误", 500, detail)


class EmbeddingTimeoutException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2008", "Embedding 超时 / 限流", 502, detail)


class ParserErrorException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2009", "解析器错误", 400, detail)


class ReprocessFailedException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2010", "重新处理失败", 400, detail)


class DocumentProcessingError(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2011", "文档正在处理中", 409, detail)


class ForceOverrideConflictException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2012", "旧文档仍在处理中，无法覆盖", 409, detail)


class DocumentNameExistsException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E2013", "文档名称已存在", 409, detail)


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


class MetaQuestionException(AppException):
    """元问题异常：用户询问助手能力等 META 类问题，无需检索。

    携带 conv 和 is_first_turn 供 chat() 构建 META SSE 响应。
    """

    def __init__(self, question: str, conv: object, is_first_turn: bool):
        super().__init__(
            "E4006", "元问题，无需检索",
            200,  # 非错误，是正常业务分流
            question[:100],
        )
        self.conv = conv
        self.is_first_turn = is_first_turn


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


class RefreshTokenExpiredException(AppException):
    def __init__(self):
        super().__init__("E5006", "Refresh Token 已过期", 401)


class RefreshTokenRevokedException(AppException):
    def __init__(self):
        super().__init__("E5007", "Refresh Token 已吊销", 401)


class InvalidRefreshTokenException(AppException):
    def __init__(self, detail: str = ""):
        super().__init__("E5008", "Refresh Token 无效或格式错误", 401, detail)


class TokenLeakDetectedException(AppException):
    def __init__(self):
        super().__init__(
            "E5009",
            "Token 可能泄露，已吊销全部会话",
            401,
            "检测到已吊销的旧 Token 被重用，已吊销该用户全部 Refresh Token",
        )


# ==================== 用户管理错误 E7xxx ====================

class TraceNotFoundException(AppException):
    def __init__(self, trace_id: str):
        super().__init__("E7001", "Trace 不存在", 404, f"trace_id={trace_id} 不存在")


class UserNotFoundException(AppException):
    def __init__(self, user_id: int):
        super().__init__("E7002", "用户不存在", 404, f"user_id={user_id} 不存在")


class AdminSelfModifyException(AppException):
    def __init__(self):
        super().__init__("E7003", "不能修改自身", 400, "管理员不能修改自己的角色或状态")


class PasswordSameAsCurrentException(AppException):
    def __init__(self):
        super().__init__("E7004", "新密码不能与原密码相同", 400, "请设置一个与当前密码不同的新密码")


# ==================== 认证错误补充 E5xxx ====================

class UserDisabledException(AppException):
    def __init__(self):
        super().__init__("E5010", "用户已被禁用", 401, "该用户账号已被管理员禁用，请联系管理员")


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
