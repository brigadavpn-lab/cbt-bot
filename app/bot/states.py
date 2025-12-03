from aiogram.fsm.state import State, StatesGroup

# Состояние для режима "Своя ситуация" (общение с ИИ)
class UserState(StatesGroup):
    waiting_for_situation = State()

# Состояние для режима "Тест" (цепочка из 10 вопросов)
class TestState(StatesGroup):
    in_progress = State()

# НОВОЕ: Состояние для режима генерации
class GenState(StatesGroup):
    active = State()