from app.generation.video_links import link_steps_to_frames
from app.schemas.instruction import InstructionStep, WorkInstruction
from app.schemas.video import FrameAnalysis, Keyframe, VideoSegment


def _instruction() -> WorkInstruction:
    return WorkInstruction(
        title="Инструкция",
        purpose="Проверка связи с видео.",
        scope="Тестовый участок.",
        operator_level="Новый оператор",
        required_ppe=["Очки"],
        required_tools=["Документ"],
        safety_requirements=["Проверить безопасность"],
        hazard_zones=["Рабочая зона"],
        prerequisites=["Рабочее место готово"],
        steps=[
            InstructionStep(
                number=1,
                action="Проверить защитное ограждение станка",
                expected_result="Ограждение закрыто",
            ),
            InstructionStep(
                number=2,
                action="Нажать кнопку запуска",
                expected_result="Станок запущен",
            ),
        ],
        control_points=["Контроль выполнен"],
        quality_checklist=["Результат проверен"],
        emergency_actions=["Остановить операцию"],
        common_mistakes=["Пропуск проверки"],
    )


def test_link_steps_to_frames_uses_text_overlap() -> None:
    links = link_steps_to_frames(
        _instruction(),
        [
            FrameAnalysis(
                frame_index=10,
                timestamp_seconds=1,
                summary="Оператор проверяет защитное ограждение станка.",
                visible_equipment=["защитное ограждение", "станок"],
                analysis_mode="openai",
            ),
            FrameAnalysis(
                frame_index=20,
                timestamp_seconds=5,
                summary="Оператор нажимает кнопку запуска.",
                operator_actions=["нажать кнопку запуска"],
                analysis_mode="openai",
            ),
        ],
        [
            Keyframe(
                frame_index=10,
                timestamp_seconds=1,
                image_path="a.jpg",
                image_url="/generated/keyframes/test/a.jpg",
            ),
            Keyframe(
                frame_index=20,
                timestamp_seconds=5,
                image_path="b.jpg",
                image_url="/generated/keyframes/test/b.jpg",
            ),
        ],
    )

    assert [link.frame_index for link in links] == [10, 20]
    assert links[0].confidence > 0.35
    assert links[0].analysis_mode == "openai"
    assert links[0].image_url == "/generated/keyframes/test/a.jpg"


def test_link_steps_to_frames_falls_back_to_sequence_without_overlap() -> None:
    links = link_steps_to_frames(
        _instruction(),
        [],
        [
            Keyframe(frame_index=1, timestamp_seconds=0, image_path="a.jpg", image_url="/generated/keyframes/test/a.jpg"),
            Keyframe(frame_index=2, timestamp_seconds=10, image_path="b.jpg", image_url="/generated/keyframes/test/b.jpg"),
        ],
    )

    assert [link.frame_index for link in links] == [1, 2]
    assert all(link.confidence == 0.2 for link in links)
    assert "по порядку" in links[0].reason


def test_link_steps_to_frames_drops_untrusted_image_urls() -> None:
    links = link_steps_to_frames(
        _instruction(),
        [
            FrameAnalysis(
                frame_index=10,
                timestamp_seconds=1,
                summary="Оператор проверяет защитное ограждение станка.",
                visible_equipment=["защитное ограждение", "станок"],
            )
        ],
        [
            Keyframe(
                frame_index=10,
                timestamp_seconds=1,
                image_path="a.jpg",
                image_url="https://example.com/tracker.jpg",
            )
        ],
    )

    assert links[0].image_url is None


def test_link_steps_to_frames_uses_temporal_order_for_ties() -> None:
    instruction = _instruction()
    shared_analysis = [
        FrameAnalysis(
            frame_index=1,
            timestamp_seconds=1,
            summary="Станок, защитное ограждение, кнопка запуска.",
            visible_equipment=["станок", "защитное ограждение", "кнопка запуска"],
        ),
        FrameAnalysis(
            frame_index=2,
            timestamp_seconds=8,
            summary="Станок, защитное ограждение, кнопка запуска.",
            visible_equipment=["станок", "защитное ограждение", "кнопка запуска"],
        ),
    ]

    links = link_steps_to_frames(
        instruction,
        shared_analysis,
        [
            Keyframe(frame_index=1, timestamp_seconds=1, image_path="a.jpg", image_url="/generated/keyframes/test/a.jpg"),
            Keyframe(frame_index=2, timestamp_seconds=8, image_path="b.jpg", image_url="/generated/keyframes/test/b.jpg"),
        ],
    )

    assert [link.frame_index for link in links] == [1, 2]


def test_link_steps_to_frames_uses_video_segment_text() -> None:
    instruction = _instruction()

    links = link_steps_to_frames(
        instruction,
        [],
        [
            Keyframe(frame_index=1, timestamp_seconds=1, image_path="a.jpg", image_url="/generated/keyframes/test/a.jpg"),
            Keyframe(frame_index=2, timestamp_seconds=8, image_path="b.jpg", image_url="/generated/keyframes/test/b.jpg"),
        ],
        [
            VideoSegment(
                segment_index=1,
                start_seconds=1,
                end_seconds=1,
                frame_indices=[1],
                summary="Оператор проверяет защитное ограждение станка.",
                dominant_actions=["проверить защитное ограждение"],
                visible_equipment=["станок", "защитное ограждение"],
            ),
            VideoSegment(
                segment_index=2,
                start_seconds=8,
                end_seconds=8,
                frame_indices=[2],
                summary="Оператор нажимает кнопку запуска.",
                dominant_actions=["нажать кнопку запуска"],
                visible_equipment=["кнопка запуска"],
            ),
        ],
    )

    assert [link.frame_index for link in links] == [1, 2]
    assert all(link.confidence > 0.2 for link in links)
