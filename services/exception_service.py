from db.dao import ExceptionLogDAO

class ExceptionService:
    @staticmethod
    def get_all_logs(handled=None):
        return ExceptionLogDAO.get_all(handled=handled)

    @staticmethod
    def mark_handled(log_id, handled_by='管理员'):
        return ExceptionLogDAO.mark_handled(log_id, handled_by)

    @staticmethod
    def get_unhandled_count():
        logs = ExceptionLogDAO.get_all(handled=False)
        return len(logs)
