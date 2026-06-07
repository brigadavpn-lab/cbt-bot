from pydantic import BaseModel, Field, field_validator


DISTORTIONS = [
    "Черно-белое мышление",
    "Чтение мыслей",
    "Сверхобобщение",
    "Катастрофизация",
    "Предсказания будущего",
    "Обесценивание",
    "Негативный фильтр",
    "Завышенные стандарты",
    "Тирания долженствования",
    "Магическое мышление",
    "Навешивание ярлыков",
    "Персонализация",
    "Обвинение",
    "Неадекватные социальные сравнения",
    "Ориентация на сожаление",
    "Эффект невозвратных затрат",
    "Ретроспективное искажение",
    "Эмоциональное обоснование",
]


class GeneratedTaskSchema(BaseModel):
    situation: str = Field(min_length=10, max_length=600)
    thought: str = Field(min_length=5, max_length=300)
    correct_cognitive_distortion: str
    options: list[str] = Field(min_length=4, max_length=4)
    explanation: str = Field(min_length=5, max_length=200)

    model_config = {"extra": "forbid"}

    @field_validator("correct_cognitive_distortion")
    @classmethod
    def distortion_in_list(cls, v: str) -> str:
        if v not in DISTORTIONS:
            raise ValueError("Неизвестное искажение")
        return v

    @field_validator("options")
    @classmethod
    def options_unique_and_valid(cls, v: list[str]) -> list[str]:
        if len(set(v)) != 4:
            raise ValueError("Варианты не уникальны")
        for opt in v:
            if opt not in DISTORTIONS:
                raise ValueError("Вариант не из списка искажений")
        return v

    @field_validator("situation", "thought", "explanation", mode="before")
    @classmethod
    def no_html(cls, v: object) -> object:
        if isinstance(v, str) and ("<" in v or ">" in v):
            raise ValueError("HTML запрещён в полях задачи")
        return v
