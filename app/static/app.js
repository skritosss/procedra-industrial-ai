const translations = {
        ru: {
          subtitle: "Генератор производственных инструкций",
          workspaceContext: "Завод 1 · Производственный контур",
          navGenerator: "Генератор",
          navInstructions: "Инструкции",
          navEditor: "Редактор",
          navExecution: "Выполнение",
          navEvaluation: "Проверки",
          navSources: "Источники",
          navVideo: "Видео",
          navHistory: "История",
          navMarkdown: "Markdown",
          navJson: "JSON",
          navCollapse: "Свернуть",
          mobileMenuOpen: "Открыть меню",
          mobileMenuClose: "Закрыть меню",
          formTitle: "Входные данные",
          formSubtitle: "Опишите производственную операцию и добавьте технический контекст.",
          taskLabel: "Задача",
          userLevelLabel: "Уровень пользователя",
          instructionTypeLabel: "Тип инструкции",
          industryProfileLabel: "Отраслевой профиль",
          operationLabel: "Название операции",
          departmentLabel: "Участок",
          equipmentLabel: "Оборудование",
          contextLabel: "Технический контекст",
          useContextLabel: "Использовать базу технической документации",
          apiTokenLabel: "API-токен",
          authGuest: "Гость",
          authOpen: "Войти",
          authLogout: "Выйти",
          authTitle: "Аккаунт",
          authMode: "Режим",
          authModeLogin: "Вход",
          authModeRegister: "Регистрация",
          authFullName: "ФИО",
          authEmail: "Email",
          authPassword: "Пароль",
          authRole: "Роль",
          authSubmit: "Продолжить",
          authLoggedIn: "Вход выполнен",
          authLoggedOut: "Вы вышли из аккаунта",
          authLogoutFailed: "Не удалось отозвать серверную сессию. Повторите выход.",
          authTokenPrompt: "API требует токен доступа. Введите токен:",
          maxSourcesLabel: "Количество источников",
          sampleCaseLabel: "Шаблон операции",
          sampleCaseButton: "Применить",
          generateButton: "Сформировать инструкцию",
          resultTitle: "Результат",
          resultSubtitle: "Структурированная инструкция, оценка структуры, Markdown и JSON.",
          tabInstruction: "Инструкция",
          tabEditor: "Редактор",
          tabExecution: "Выполнение",
          tabEvaluation: "Оценка",
          tabSources: "Источники",
          tabVideo: "Видео",
          tabHistory: "История",
          tabMarkdown: "Markdown",
          tabJson: "JSON",
          statusIdle: "Готово к генерации",
          statusLoading: "Формирование...",
          statusReady: "Готово",
          statusError: "Ошибка генерации",
          exportMarkdown: "Скачать MD",
          exportPdf: "Скачать PDF",
          exportJson: "Скачать JSON",
          improveInstruction: "Довести качество",
          editorTitle: "Редактор инструкции",
          instructionTitle: "Название инструкции",
          scope: "Область применения",
          editorApply: "Применить правки",
          editorImprove: "Довести качество инструкции",
          editorSaved: "Правки применены",
          editorImproved: "Качество инструкции обновлено",
          editorMainFields: "Основные поля",
          editorScope: "Область применения",
          editorSafetyFields: "Безопасность и подготовка",
          editorReviewFields: "Проверка и внедрение",
          editorSteps: "Шаги выполнения",
          editorListHint: "Один пункт на строку",
          executionTitle: "Операторский чеклист",
          executionMeta: "Отмечайте выполнение шагов во время пробного прохода. Итоговые замечания перенесите в историю версии или локальный журнал.",
          executionSteps: "Выполнение шагов",
          executionQuality: "Контроль качества",
          executionExecutor: "Исполнитель",
          executionExecutorPlaceholder: "Например: оператор Иванов И.И.",
          executionNotes: "Замечания по выполнению",
          executionNotesPlaceholder: "Например: шаг 3 требует уточнения допуска, оператор не нашел нужную маркировку.",
          executionSave: "Сохранить выполнение",
          executionSaved: "Выполнение сохранено",
          executionSaveUnavailable: "Сначала сохраните версию инструкции в историю.",
          shopFloorMode: "Режим цеха",
          shopFloorModeHint: "Крупные элементы для планшета и пошагового прохода на рабочем месте.",
          saveHistory: "Сохранить версию",
          historyTitle: "Сохраненные версии",
          historyEmpty: "Сохраненных версий пока нет",
          historyOpen: "Открыть",
          historySaved: "Версия сохранена",
          historyLoading: "Загрузка истории...",
          historyVersion: "Версия",
          historyCreated: "Создано",
          historySources: "Источников",
          historySteps: "Шагов",
          historyReviewer: "Проверяющий",
          workflowReviewerRole: "Роль проверяющего",
          historyComment: "Комментарий",
          historySendReview: "На проверку",
          historyApprove: "Утвердить",
          historyReject: "Отклонить",
          historyUpdated: "Статус версии обновлен",
          auditTrailTitle: "Журнал аудита",
          auditEventCreated: "Создано",
          auditEventActor: "Участник",
          auditEventTransition: "Переход",
          auditEventComment: "Комментарий",
          auditEventMetadata: "Метаданные",
          auditEventTypes: {
            version_saved: "Версия сохранена",
            workflow_updated: "Статус изменен",
            execution_saved: "Выполнение сохранено",
          },
          executionSummaryTitle: "Сводка выполнения",
          executionSummaryRuns: "Пробных прогонов",
          executionSummarySteps: "Выполнено шагов",
          executionSummaryQuality: "Контроль качества",
          executionSummaryLatest: "Последние выполнения",
          workflowDecisionTitle: "Решение по версии",
          workflowResolvedBlockers: "Закрытые блокеры",
          workflowResolvedBlockersPlaceholder: "Один закрытый блокер на строку. Заполняется при утверждении или возврате после проверки.",
          workflowSubmit: "Зафиксировать решение",
          workflowCancel: "Отмена",
          reviewerRoles: {
            master: "Мастер смены / руководитель участка",
            technologist: "Инженер / технолог",
            safety: "Охрана труда / промышленная безопасность",
            quality: "Специалист по качеству",
            admin: "Администратор",
          },
          userRoles: {
            operator: "Оператор",
            master: "Мастер смены / руководитель участка",
            technologist: "Инженер / технолог",
            safety: "Охрана труда / промышленная безопасность",
            quality: "Специалист по качеству",
            admin: "Администратор",
          },
          emptyTitle: "Результат появится здесь",
          emptyBody: "Заполните форму и запустите генерацию.",
          purpose: "Назначение",
          passport: "Паспорт инструкции",
          workflowStatus: "Статус жизненного цикла",
          approvalRoles: "Роли для согласования",
          approvalBlockers: "Блокеры перед утверждением",
          workflowNextActions: "Следующие действия по внедрению",
          responsibilityMatrix: "Матрица ответственности",
          observedFacts: "Утверждения из входных данных",
          evidenceProvenance: "Происхождение и статус утверждений",
          safetyFindings: "Safety-блокеры",
          localVerificationRequired: "Что требуется проверить локально",
          expertReviewQuestions: "Вопросы для экспертной проверки",
          department: "Участок",
          equipment: "Оборудование",
          operatorLevel: "Уровень пользователя",
          ppe: "СИЗ",
          tools: "Инструменты и документы",
          safety: "Требования безопасности",
          hazards: "Опасные зоны",
          prerequisites: "Предварительные условия",
          steps: "Порядок выполнения",
          expectedResult: "Ожидаемый результат",
          safetyNote: "Безопасность",
          verification: "Проверка",
          commonMistakes: "Типовые ошибки",
          controlPoints: "Контрольные точки",
          acceptanceCriteria: "Критерии приемки результата",
          qualityChecklist: "Чеклист качества",
          emergencyActions: "Действия при нештатной ситуации",
          implementationLimits: "Ограничения и проверка перед внедрением",
          generationMode: "Режим",
          generationModeLabels: { model: "Языковая модель", deterministic: "Детерминированный шаблон" },
          overallScore: "Балл структуры",
          regulatorySources: "Сверено с документами",
          regulatoryBasis: "Обязательные разделы сверяются с приказом Минтруда России № 772н от 29.10.2021. Проверяется наличие раздела, а не его правильность.",
          verdict: "Вердикт",
          riskLevel: "Уровень риска",
          expertReview: "Экспертная проверка",
          expertReviewRequired: "Требуется",
          expertReviewOptional: "Не требуется",
          criteria: "Критерии",
          strengths: "Сильные стороны",
          issues: "Замечания",
          missingElements: "Недостающие элементы",
          recommendations: "Рекомендации",
          sourceTitle: "Найденные источники",
          sourceExplanation:
            "Сейчас источники складываются из текста формы, локальной базы технической документации, описания/субтитров видео и анализа ключевых кадров.",
          sourceScore: "Релевантность",
          sourcePath: "Файл",
          sourceUrl: "URL",
          sourceType: "Тип источника",
          sourceAuthority: "Орган/площадка",
          sourceDocumentType: "Тип документа",
          sourceProfiles: "Профили применимости",
          sourceContribution: "Почему выбран",
          sourceTypeLocal: "Локальная база",
          sourceTypePublic: "Открытый интернет-источник",
          sourceInfluence: "Влияние на инструкцию",
          matchedTerms: "Совпавшие термины",
          noSources: "Источники не найдены",
          videoToolsTitle: "Видео и визуальный контекст",
          videoToolsDescription: "Загрузите файл или укажите ссылку, чтобы извлечь ключевые кадры перед генерацией.",
          videoUrlLabel: "Ссылка на видео",
          videoFileLabel: "Видео для анализа",
          chooseFile: "Выбрать файл",
          noFileSelected: "Файл не выбран",
          maxKeyframesLabel: "Ключевых кадров",
          visualQualityLabel: "Качество кадров",
          visualQualityFast: "240p - быстро",
          visualQualityBalanced: "360p - баланс",
          visualQualityDetailed: "720p - детально",
          visualQualityMax: "1080p - максимум",
          extractVideoButton: "Извлечь ключевые кадры",
          generateFromVideoButton: "Сформировать инструкцию по видео",
          videoStatusLoading: "Обработка видео...",
          videoStatusProgress: "Обработка видео: {progress}%",
          videoStatusCancelRequested: "Запрошена отмена обработки...",
          videoStatusCancelled: "Обработка видео отменена",
          videoStatusFailed: "Не удалось обработать видео",
          cancelVideoJob: "Отменить обработку",
          videoStatusReady: "Кадры извлечены",
          videoInstructionLoading: "Формирование инструкции по видео...",
          videoStatusNoInput: "Вставьте ссылку или выберите видеофайл",
          videoStatusBothInputs: "Оставьте либо ссылку, либо файл",
          videoStatusNoProcessedVideo: "Сначала извлеките данные из видео",
          videoStatusNoKeyframes: "В видео не найдено ключевых кадров для инструкции",
          documentFileLabel: "Документ предприятия",
          documentToolsTitle: "Документы предприятия",
          documentToolsDescription: "Добавьте локальный документ в базу источников для следующих генераций.",
          uploadDocumentButton: "Загрузить документ",
          documentUploadLoading: "Загрузка документа...",
          documentUploadReady: "Документ добавлен в источники",
          documentStatusNoFile: "Выберите документ .txt, .md или .pdf",
          documentListTitle: "Загруженные документы",
          documentListEmpty: "Документы предприятия пока не загружены",
          documentStoredAs: "Индекс",
          documentCharacters: "Символов извлечено",
          videoTitle: "Ключевые кадры",
          videoMeta: "Параметры видео",
          videoContextTitle: "Контекст из видео",
          videoSegmentsTitle: "Смысловые этапы видео",
          videoSegment: "Этап",
          videoSegmentRange: "Диапазон",
          videoSegmentFrames: "Кадры",
          videoSegmentActions: "Действия этапа",
          videoSegmentEquipment: "Оборудование/объекты этапа",
          videoSegmentSafety: "Риски и безопасность этапа",
          frameAnalysisTitle: "Анализ кадров",
          frameAnalysisMode: "Режим анализа",
          visibleEquipment: "Оборудование/объекты",
          operatorActions: "Действия оператора",
          safetyObservations: "Безопасность",
          ppeObservations: "СИЗ",
          potentialHazards: "Потенциальные опасности",
          uncertainties: "Неопределенности",
          videoSource: "Источник",
          videoDuration: "Длительность",
          videoTotalFrames: "Всего кадров в видео",
          videoVisualQuality: "Качество кадров",
          videoNotes: "Примечания",
          frame: "Кадр",
          timestamp: "Время",
          frameSelectionScore: "Оценка кадра",
          frameSelectionReason: "Почему выбран",
          stepFrameLink: "Связь с видео",
          linkReason: "Причина",
          confidence: "Уверенность",
          noVideo: "Видео пока не обработано",
          noIssues: "Замечаний нет",
          noData: "Не указано",
          criterionLabels: {
            completeness: "Полнота",
            clarity: "Понятность",
            input_alignment: "Соответствие входным данным",
            request_focus: "Фокус на задаче",
            safety: "Безопасность",
            logical_sequence: "Логическая последовательность",
            training_value: "Пригодность для обучения",
            source_grounding: "Опора на источники",
            domain_risk_control: "Контроль отраслевых рисков",
            implementation_readiness: "Готовность к внедрению",
            executability: "Исполнимость на месте",
            regulatory_structure: "Соответствие обязательной структуре",
          },
          riskLabels: {
            low: "Низкий",
            medium: "Средний",
            high: "Высокий",
            critical: "Критический",
          },
          taskPlaceholder: "Например: подготовить рабочее место оператора перед запуском оборудования",
          operationPlaceholder: "Подготовка рабочего места перед запуском",
          departmentPlaceholder: "Кузнечно-прессовый участок",
          equipmentPlaceholder: "Рабочее место оператора",
          contextPlaceholder:
            "Перед запуском проверить защитные ограждения, аварийную кнопку и отсутствие посторонних предметов.",
          languageAria: "Язык интерфейса",
          navAria: "Основная навигация",
          routeAria: "Ход согласования",
          routeDraft: "Черновик",
          routeReview: "На проверке",
          routeApproved: "Утверждено",
          toolsToggleHint: "Развернуть",
          videoUrlPlaceholder: "Ссылка на видео",
          levels: {
            new_operator: "Новый оператор",
            experienced_operator: "Опытный оператор",
            engineer: "Инженер/технолог",
          },
          types: {
            workplace_preparation: "Подготовка рабочего места",
            equipment_startup: "Запуск оборудования",
            equipment_shutdown: "Остановка оборудования",
            inspection: "Контроль и проверка",
            training: "Обучение сотрудника",
            maintenance: "Техническое обслуживание",
            general: "Общая операция",
          },
          profiles: {
            manufacturing: "Производство",
            construction: "Строительство",
            occupational_safety: "Охрана труда",
            emergency_response: "МЧС/аварийное реагирование",
            public_service: "Госуслуги/госслужба",
            housing_utilities: "ЖКХ",
            healthcare: "Медицина",
            education: "Образование",
            food_production: "Пищевая промышленность",
            transport: "Транспорт",
            information_security: "Информационная безопасность",
            general: "Общий профиль",
          },
        },
        en: {
          subtitle: "Manufacturing work instruction generator",
          workspaceContext: "Plant 1 · Production workspace",
          navGenerator: "Generator",
          navInstructions: "Instructions",
          navEditor: "Editor",
          navExecution: "Execution",
          navEvaluation: "Checks",
          navSources: "Sources",
          navVideo: "Video",
          navHistory: "History",
          navMarkdown: "Markdown",
          navJson: "JSON",
          navCollapse: "Collapse",
          mobileMenuOpen: "Open menu",
          mobileMenuClose: "Close menu",
          formTitle: "Input",
          formSubtitle: "Describe a production operation and add technical context.",
          taskLabel: "Task",
          userLevelLabel: "User level",
          instructionTypeLabel: "Instruction type",
          industryProfileLabel: "Industry profile",
          operationLabel: "Operation name",
          departmentLabel: "Department",
          equipmentLabel: "Equipment",
          contextLabel: "Technical context",
          useContextLabel: "Use technical documentation base",
          apiTokenLabel: "API token",
          authGuest: "Guest",
          authOpen: "Sign in",
          authLogout: "Sign out",
          authTitle: "Account",
          authMode: "Mode",
          authModeLogin: "Login",
          authModeRegister: "Register",
          authFullName: "Full name",
          authEmail: "Email",
          authPassword: "Password",
          authRole: "Role",
          authSubmit: "Continue",
          authLoggedIn: "Signed in",
          authLoggedOut: "Signed out",
          authLogoutFailed: "Could not revoke the server session. Try signing out again.",
          authTokenPrompt: "API access token is required. Enter token:",
          maxSourcesLabel: "Number of sources",
          sampleCaseLabel: "Operation template",
          sampleCaseButton: "Apply",
          generateButton: "Generate instruction",
          resultTitle: "Result",
          resultSubtitle: "Structured instruction, structural evaluation, Markdown, and JSON.",
          tabInstruction: "Instruction",
          tabEditor: "Editor",
          tabExecution: "Run",
          tabEvaluation: "Evaluation",
          tabSources: "Sources",
          tabVideo: "Video",
          tabHistory: "History",
          tabMarkdown: "Markdown",
          tabJson: "JSON",
          statusIdle: "Ready",
          statusLoading: "Generating...",
          statusReady: "Ready",
          statusError: "Generation error",
          exportMarkdown: "Download MD",
          exportPdf: "Download PDF",
          exportJson: "Download JSON",
          improveInstruction: "Improve quality",
          editorTitle: "Instruction editor",
          instructionTitle: "Instruction title",
          scope: "Scope",
          editorApply: "Apply edits",
          editorImprove: "Improve instruction quality",
          editorSaved: "Edits applied",
          editorImproved: "Instruction quality updated",
          editorMainFields: "Main fields",
          editorScope: "Scope",
          editorSafetyFields: "Safety and preparation",
          editorReviewFields: "Review and rollout",
          editorSteps: "Execution steps",
          editorListHint: "One item per line",
          executionTitle: "Operator checklist",
          executionMeta: "Check off steps during a trial run. Move final notes into version history or the local log.",
          executionSteps: "Step execution",
          executionQuality: "Quality control",
          executionExecutor: "Executor",
          executionExecutorPlaceholder: "Example: operator Ivanov I.I.",
          executionNotes: "Execution notes",
          executionNotesPlaceholder: "Example: step 3 needs tolerance clarification; operator could not find the required marking.",
          executionSave: "Save execution",
          executionSaved: "Execution saved",
          executionSaveUnavailable: "Save this instruction version to history first.",
          shopFloorMode: "Shop-floor mode",
          shopFloorModeHint: "Larger controls for tablet-based step execution at the workplace.",
          saveHistory: "Save version",
          historyTitle: "Saved versions",
          historyEmpty: "No saved versions yet",
          historyOpen: "Open",
          historySaved: "Version saved",
          historyLoading: "Loading history...",
          historyVersion: "Version",
          historyCreated: "Created",
          historySources: "Sources",
          historySteps: "Steps",
          historyReviewer: "Reviewer",
          workflowReviewerRole: "Reviewer role",
          historyComment: "Comment",
          historySendReview: "Send to review",
          historyApprove: "Approve",
          historyReject: "Reject",
          historyUpdated: "Version status updated",
          auditTrailTitle: "Audit trail",
          auditEventCreated: "Created",
          auditEventActor: "Actor",
          auditEventTransition: "Transition",
          auditEventComment: "Comment",
          auditEventMetadata: "Metadata",
          auditEventTypes: {
            version_saved: "Version saved",
            workflow_updated: "Workflow updated",
            execution_saved: "Execution saved",
          },
          executionSummaryTitle: "Execution summary",
          executionSummaryRuns: "Trial runs",
          executionSummarySteps: "Completed steps",
          executionSummaryQuality: "Quality checks",
          executionSummaryLatest: "Latest executions",
          workflowDecisionTitle: "Version decision",
          workflowResolvedBlockers: "Resolved blockers",
          workflowResolvedBlockersPlaceholder: "One resolved blocker per line. Use for approval or review return evidence.",
          workflowSubmit: "Record decision",
          workflowCancel: "Cancel",
          reviewerRoles: {
            master: "Shift master / area lead",
            technologist: "Engineer / technologist",
            safety: "Occupational / industrial safety",
            quality: "Quality specialist",
            admin: "Administrator",
          },
          userRoles: {
            operator: "Operator",
            master: "Shift master / area lead",
            technologist: "Engineer / technologist",
            safety: "Occupational / industrial safety",
            quality: "Quality specialist",
            admin: "Administrator",
          },
          emptyTitle: "The result will appear here",
          emptyBody: "Fill in the form and run generation.",
          purpose: "Purpose",
          passport: "Instruction passport",
          workflowStatus: "Lifecycle status",
          approvalRoles: "Approval roles",
          approvalBlockers: "Approval blockers",
          workflowNextActions: "Next implementation actions",
          responsibilityMatrix: "Responsibility matrix",
          observedFacts: "Input claims",
          evidenceProvenance: "Claim provenance and status",
          safetyFindings: "Safety blockers",
          localVerificationRequired: "Local verification required",
          expertReviewQuestions: "Expert review questions",
          department: "Department",
          equipment: "Equipment",
          operatorLevel: "User level",
          ppe: "PPE",
          tools: "Tools and documents",
          safety: "Safety requirements",
          hazards: "Hazard zones",
          prerequisites: "Prerequisites",
          steps: "Steps",
          expectedResult: "Expected result",
          safetyNote: "Safety",
          verification: "Verification",
          commonMistakes: "Common mistakes",
          controlPoints: "Control points",
          acceptanceCriteria: "Acceptance criteria",
          qualityChecklist: "Quality checklist",
          emergencyActions: "Emergency actions",
          implementationLimits: "Implementation limits and review",
          generationMode: "Mode",
          generationModeLabels: { model: "Language model", deterministic: "Deterministic template" },
          overallScore: "Structure score",
          regulatorySources: "Checked against",
          regulatoryBasis: "Mandatory sections are checked against Order 772n of the Ministry of Labour of Russia (29.10.2021). Presence of a section is checked, not its correctness.",
          verdict: "Verdict",
          riskLevel: "Risk level",
          expertReview: "Expert review",
          expertReviewRequired: "Required",
          expertReviewOptional: "Not required",
          criteria: "Criteria",
          strengths: "Strengths",
          issues: "Issues",
          missingElements: "Missing elements",
          recommendations: "Recommendations",
          sourceTitle: "Retrieved sources",
          sourceExplanation:
            "Current sources are form text, the local technical documentation base, video description/subtitles, and keyframe analysis.",
          sourceScore: "Relevance",
          sourcePath: "File",
          sourceUrl: "URL",
          sourceType: "Source type",
          sourceAuthority: "Authority/platform",
          sourceDocumentType: "Document type",
          sourceProfiles: "Applicable profiles",
          sourceContribution: "Why selected",
          sourceTypeLocal: "Local base",
          sourceTypePublic: "Public internet source",
          sourceInfluence: "Instruction influence",
          matchedTerms: "Matched terms",
          noSources: "No sources found",
          videoToolsTitle: "Video and visual context",
          videoToolsDescription: "Upload a file or provide a URL to extract keyframes before generation.",
          videoUrlLabel: "Video URL",
          videoFileLabel: "Video for analysis",
          chooseFile: "Choose file",
          noFileSelected: "No file selected",
          maxKeyframesLabel: "Keyframes",
          visualQualityLabel: "Frame quality",
          visualQualityFast: "240p - fast",
          visualQualityBalanced: "360p - balanced",
          visualQualityDetailed: "720p - detailed",
          visualQualityMax: "1080p - maximum",
          extractVideoButton: "Extract keyframes",
          generateFromVideoButton: "Generate from video",
          videoStatusLoading: "Processing video...",
          videoStatusProgress: "Processing video: {progress}%",
          videoStatusCancelRequested: "Cancelling video processing...",
          videoStatusCancelled: "Video processing cancelled",
          videoStatusFailed: "Video processing failed",
          cancelVideoJob: "Cancel processing",
          videoStatusReady: "Keyframes extracted",
          videoInstructionLoading: "Generating from video...",
          videoStatusNoInput: "Paste a video URL or choose a video file",
          videoStatusBothInputs: "Use either a URL or a file",
          videoStatusNoProcessedVideo: "Extract video data first",
          videoStatusNoKeyframes: "No keyframes were found for instruction generation",
          documentFileLabel: "Enterprise document",
          documentToolsTitle: "Enterprise documents",
          documentToolsDescription: "Add a local document to the source base for future generations.",
          uploadDocumentButton: "Upload document",
          documentUploadLoading: "Uploading document...",
          documentUploadReady: "Document added to sources",
          documentStatusNoFile: "Choose a .txt, .md, or .pdf document",
          documentListTitle: "Uploaded documents",
          documentListEmpty: "No enterprise documents uploaded yet",
          documentStoredAs: "Index",
          documentCharacters: "Extracted characters",
          videoTitle: "Keyframes",
          videoMeta: "Video metadata",
          videoContextTitle: "Video context",
          videoSegmentsTitle: "Video stages",
          videoSegment: "Stage",
          videoSegmentRange: "Range",
          videoSegmentFrames: "Frames",
          videoSegmentActions: "Stage actions",
          videoSegmentEquipment: "Stage equipment/objects",
          videoSegmentSafety: "Stage risks and safety",
          frameAnalysisTitle: "Frame analysis",
          frameAnalysisMode: "Analysis mode",
          visibleEquipment: "Equipment/objects",
          operatorActions: "Operator actions",
          safetyObservations: "Safety",
          ppeObservations: "PPE",
          potentialHazards: "Potential hazards",
          uncertainties: "Uncertainties",
          videoSource: "Source",
          videoDuration: "Duration",
          videoTotalFrames: "Total frames in video",
          videoVisualQuality: "Frame quality",
          videoNotes: "Notes",
          frame: "Frame",
          timestamp: "Time",
          frameSelectionScore: "Frame score",
          frameSelectionReason: "Why selected",
          stepFrameLink: "Video link",
          linkReason: "Reason",
          confidence: "Confidence",
          noVideo: "No video has been processed yet",
          noIssues: "No issues",
          noData: "Not specified",
          criterionLabels: {
            completeness: "Completeness",
            clarity: "Clarity",
            input_alignment: "Input alignment",
            request_focus: "Request focus",
            safety: "Safety",
            logical_sequence: "Logical sequence",
            training_value: "Training value",
            source_grounding: "Source grounding",
            domain_risk_control: "Domain risk control",
            implementation_readiness: "Implementation readiness",
            executability: "Executability on site",
            regulatory_structure: "Mandatory structure compliance",
          },
          riskLabels: {
            low: "Low",
            medium: "Medium",
            high: "High",
            critical: "Critical",
          },
          taskPlaceholder: "For example: prepare the operator workplace before equipment startup",
          operationPlaceholder: "Workplace preparation before startup",
          departmentPlaceholder: "Forging and pressing area",
          equipmentPlaceholder: "Operator workplace",
          contextPlaceholder:
            "Before startup, check guards, emergency stop, and absence of foreign objects.",
          languageAria: "Interface language",
          navAria: "Main navigation",
          routeAria: "Approval progress",
          routeDraft: "Draft",
          routeReview: "In review",
          routeApproved: "Approved",
          toolsToggleHint: "Expand",
          videoUrlPlaceholder: "Video URL",
          levels: {
            new_operator: "New operator",
            experienced_operator: "Experienced operator",
            engineer: "Engineer/technologist",
          },
          types: {
            workplace_preparation: "Workplace preparation",
            equipment_startup: "Equipment startup",
            equipment_shutdown: "Equipment shutdown",
            inspection: "Inspection",
            training: "Employee training",
            maintenance: "Maintenance",
            general: "General operation",
          },
          profiles: {
            manufacturing: "Manufacturing",
            construction: "Construction",
            occupational_safety: "Occupational safety",
            emergency_response: "Emergency response",
            public_service: "Public service",
            housing_utilities: "Housing and utilities",
            healthcare: "Healthcare",
            education: "Education",
            food_production: "Food production",
            transport: "Transport",
            information_security: "Information security",
            general: "General",
          },
        },
      };

      const optionValues = {
        user_level: ["new_operator", "experienced_operator", "engineer"],
        instruction_type: [
          "workplace_preparation",
          "equipment_startup",
          "equipment_shutdown",
          "inspection",
          "training",
          "maintenance",
          "general",
        ],
        industry_profile: [
          "manufacturing",
          "construction",
          "occupational_safety",
          "emergency_response",
          "public_service",
          "housing_utilities",
          "healthcare",
          "education",
          "food_production",
          "transport",
          "information_security",
          "general",
        ],
      };

      const sampleCases = [
        {
          id: "workplace_preparation",
          labels: {
            ru: "Подготовка рабочего места",
            en: "Workplace preparation",
          },
          payload: {
            task: "Подготовить рабочее место оператора перед началом смены на производственном участке",
            user_level: "new_operator",
            instruction_type: "workplace_preparation",
            industry_profile: "manufacturing",
            department: "Кузнечно-прессовый участок",
            equipment: "Рабочее место оператора производственного оборудования",
            operation_name: "Подготовка рабочего места перед началом смены",
            technical_context:
              "Перед началом работы оператор должен проверить чистоту рабочей зоны, наличие СИЗ, доступность аварийной остановки, исправность защитных ограждений и отсутствие посторонних предметов возле оборудования.",
          },
        },
        {
          id: "equipment_startup",
          labels: {
            ru: "Подготовка оборудования к запуску",
            en: "Equipment startup preparation",
          },
          payload: {
            task: "Выполнить безопасную подготовку оборудования к запуску после приемки смены",
            user_level: "experienced_operator",
            instruction_type: "equipment_startup",
            industry_profile: "manufacturing",
            department: "Производственный участок",
            equipment: "Станочное или прессовое оборудование",
            operation_name: "Подготовка оборудования к запуску",
            technical_context:
              "Запуск разрешается только после внешнего осмотра оборудования, проверки зоны движения рабочих органов, подтверждения готовности инструмента и отсутствия замечаний в журнале смены.",
          },
        },
        {
          id: "equipment_shutdown",
          labels: {
            ru: "Остановка и передача смены",
            en: "Shutdown and shift handover",
          },
          payload: {
            task: "Остановить оборудование после завершения операции и подготовить рабочее место к передаче смены",
            user_level: "experienced_operator",
            instruction_type: "equipment_shutdown",
            industry_profile: "manufacturing",
            department: "Производственный участок",
            equipment: "Производственное оборудование участка",
            operation_name: "Остановка оборудования и передача смены",
            technical_context:
              "После завершения операции оператор должен привести оборудование в безопасное состояние, убрать инструмент из рабочей зоны, зафиксировать замечания и сообщить мастеру смены о нестандартных ситуациях.",
          },
        },
        {
          id: "inspection_guarding",
          labels: {
            ru: "Осмотр ограждений и аварийной остановки",
            en: "Guarding and emergency-stop inspection",
          },
          payload: {
            task: "Проверить защитные ограждения и аварийную остановку оборудования перед началом работы",
            user_level: "new_operator",
            instruction_type: "inspection",
            industry_profile: "occupational_safety",
            department: "Производственный участок",
            equipment: "Оборудование с подвижными рабочими органами",
            operation_name: "Предсменная проверка ограждений и аварийной остановки",
            technical_context:
              "Проверка должна подтвердить наличие и исправность ограждений, свободный доступ к аварийной кнопке, отсутствие блокировки органов управления и отсутствие людей в опасной зоне. Все отклонения фиксируются и передаются мастеру смены.",
          },
        },
        {
          id: "maintenance_lockout",
          labels: {
            ru: "ТО с отключением энергии",
            en: "Maintenance with energy isolation",
          },
          payload: {
            task: "Подготовить оборудование к безопасному техническому обслуживанию с отключением источников энергии",
            user_level: "engineer",
            instruction_type: "maintenance",
            industry_profile: "manufacturing",
            department: "Ремонтная зона",
            equipment: "Производственное оборудование с электрическими и механическими приводами",
            operation_name: "Подготовка к техническому обслуживанию",
            technical_context:
              "Перед обслуживанием требуется остановить оборудование, исключить самопроизвольный запуск, снять остаточную энергию, обозначить зону работ, проверить отсутствие движения рабочих органов и назначить ответственное лицо.",
          },
        },
        {
          id: "construction_hot_work",
          labels: {
            ru: "Допуск к огневым работам",
            en: "Hot-work permit preparation",
          },
          payload: {
            task: "Подготовить рабочую зону к безопасному выполнению огневых работ на строительной площадке",
            user_level: "experienced_operator",
            instruction_type: "workplace_preparation",
            industry_profile: "construction",
            department: "Строительная площадка",
            equipment: "Сварочное оборудование и средства пожаротушения",
            operation_name: "Подготовка зоны огневых работ",
            technical_context:
              "До начала работ необходимо проверить наряд-допуск, удалить горючие материалы, подготовить огнетушитель, назначить наблюдающего, оградить зону и подтвердить готовность СИЗ. После работ требуется контроль зоны на отсутствие тления.",
          },
        },
        {
          id: "emergency_evacuation",
          labels: {
            ru: "Эвакуация при пожарной тревоге",
            en: "Fire alarm evacuation",
          },
          payload: {
            task: "Организовать действия персонала при пожарной тревоге и эвакуации из производственного помещения",
            user_level: "new_operator",
            instruction_type: "training",
            industry_profile: "emergency_response",
            department: "Производственное помещение",
            equipment: "Система оповещения, эвакуационные выходы, первичные средства пожаротушения",
            operation_name: "Действия при пожарной тревоге",
            technical_context:
              "Персонал должен прекратить работу, привести оборудование в безопасное состояние только если это не задерживает эвакуацию, покинуть помещение по маршруту, не пользоваться лифтами, сообщить руководителю и не возвращаться без разрешения.",
          },
        },
        {
          id: "housing_utilities_gas",
          labels: {
            ru: "Заявка о запахе газа",
            en: "Gas smell report handling",
          },
          payload: {
            task: "Обработать обращение жильца о запахе газа в помещении и передать информацию аварийной службе",
            user_level: "new_operator",
            instruction_type: "general",
            industry_profile: "housing_utilities",
            department: "Диспетчерская служба ЖКХ",
            equipment: "Система регистрации заявок и телефонная связь",
            operation_name: "Обработка аварийного обращения о запахе газа",
            technical_context:
              "Диспетчер должен уточнить адрес, контакт, признаки опасности, предупредить заявителя не пользоваться открытым огнем и электроприборами, рекомендовать проветривание и эвакуацию при угрозе, затем немедленно передать заявку в аварийную газовую службу.",
          },
        },
        {
          id: "food_sanitation",
          labels: {
            ru: "Санитарная обработка линии",
            en: "Food line sanitation",
          },
          payload: {
            task: "Провести санитарную обработку производственной линии перед запуском пищевой продукции",
            user_level: "experienced_operator",
            instruction_type: "workplace_preparation",
            industry_profile: "food_production",
            department: "Пищевое производство",
            equipment: "Производственная линия и моечный инвентарь",
            operation_name: "Санитарная подготовка линии",
            technical_context:
              "Перед запуском требуется удалить остатки сырья, выполнить мойку и дезинфекцию по локальной карте, проверить отсутствие посторонних предметов, состояние контактных поверхностей, маркировку инвентаря и запись в журнале санитарной обработки.",
          },
        },
        {
          id: "transport_pretrip",
          labels: {
            ru: "Предрейсовый осмотр транспорта",
            en: "Pre-trip vehicle inspection",
          },
          payload: {
            task: "Выполнить предрейсовый осмотр транспортного средства перед выездом на маршрут",
            user_level: "experienced_operator",
            instruction_type: "inspection",
            industry_profile: "transport",
            department: "Транспортный участок",
            equipment: "Транспортное средство",
            operation_name: "Предрейсовый осмотр",
            technical_context:
              "Перед выездом водитель должен проверить внешний осмотр, световые приборы, тормозную систему, шины, зеркала, аптечку, огнетушитель, документы и отсутствие видимых неисправностей. Выезд запрещается при критичных отклонениях.",
          },
        },
        {
          id: "security_phishing",
          labels: {
            ru: "Фишинговое письмо",
            en: "Phishing email handling",
          },
          payload: {
            task: "Обработать подозрительное фишинговое письмо без раскрытия учетных данных и заражения рабочего места",
            user_level: "new_operator",
            instruction_type: "training",
            industry_profile: "information_security",
            department: "Офисное рабочее место",
            equipment: "Корпоративная почта и рабочий компьютер",
            operation_name: "Действия при подозрительном письме",
            technical_context:
              "Сотрудник не должен переходить по ссылкам, открывать вложения, вводить пароль или пересылать письмо внешним адресатам. Необходимо сохранить признаки письма, сообщить в ИБ по установленному каналу и дождаться инструкции.",
          },
        },
      ];

      let language = localStorage.getItem("language") || "ru";
      let activeTab = "instruction";
      let lastPayload = null;
      let lastVideoPayload = null;
      let currentVideoJobId = sessionStorage.getItem("currentVideoJobId") || "";
      let historyRecords = [];
      let currentHistoryRecord = null;
      let currentAuditEvents = [];
      let executionSummary = null;
      let pendingWorkflowDecision = null;
      let currentUser = null;
      let authCapabilities = {
        public_registration_enabled: false,
        role_self_assignment_enabled: false,
        allowed_registration_roles: ["operator"],
        minimum_password_length: 8,
      };
      let shopFloorMode = localStorage.getItem("shopFloorMode") === "true";

      // Remove credentials left by pre-cookie builds; session tokens must never
      // remain available to JavaScript or persistent browser storage.
      localStorage.removeItem("authAccessToken");
      localStorage.removeItem("apiAccessToken");

      const form = document.getElementById("instruction-form");
      const sampleButton = document.getElementById("sample-button");
      const videoButton = document.getElementById("video-button");
      const videoGenerateButton = document.getElementById("video-generate-button");
      const videoCancelButton = document.getElementById("video-cancel-button");
      const videoJobProgress = document.getElementById("video-job-progress");
      const videoJobProgressBar = document.getElementById("video-job-progress-bar");
      const videoJobProgressLabel = document.getElementById("video-job-progress-label");
      const documentButton = document.getElementById("document-button");
      const improveInstructionButton = document.getElementById("improve-instruction");
      const saveHistoryButton = document.getElementById("save-history");
      const exportMarkdownButton = document.getElementById("export-markdown");
      const exportPdfButton = document.getElementById("export-pdf");
      const exportJsonButton = document.getElementById("export-json");
      const result = document.getElementById("result");
      const status = document.getElementById("status");
      const apiTokenInput = document.getElementById("api_token");
      const authState = document.getElementById("auth-state");
      const authOpenButton = document.getElementById("auth-open");
      const authLogoutButton = document.getElementById("auth-logout");
      const authModal = document.getElementById("auth-modal");
      const authForm = document.getElementById("auth-form");
      const authModeSelect = document.getElementById("auth_mode");
      const authFullNameInput = document.getElementById("auth_full_name");
      const authEmailInput = document.getElementById("auth_email");
      const authPasswordInput = document.getElementById("auth_password");
      const authRoleSelect = document.getElementById("auth_role");
      const authCancelButton = document.getElementById("auth-cancel");
      const workflowModal = document.getElementById("workflow-modal");
      const workflowForm = document.getElementById("workflow-form");
      const workflowReviewerInput = document.getElementById("workflow_reviewer");
      const workflowReviewerRoleSelect = document.getElementById("workflow_reviewer_role");
      const workflowCommentInput = document.getElementById("workflow_comment");
      const workflowResolvedBlockersInput = document.getElementById("workflow_resolved_blockers");
      const workflowCancelButton = document.getElementById("workflow-cancel");
      const reviewerRoleValues = ["master", "technologist", "safety", "quality", "admin"];
      const userRoleValues = ["operator", "master", "technologist", "safety", "quality", "admin"];
      const tabButtons = Array.from(document.querySelectorAll("[data-result-view]"));
      let authModalOpener = null;
      let workflowModalOpener = null;

      apiTokenInput.value = "";

      function t(key) {
        return translations[language][key];
      }

      function localizeStaticText() {
        document.documentElement.lang = language;
        document.querySelectorAll("[data-i18n]").forEach((element) => {
          element.textContent = t(element.dataset.i18n);
        });
        document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
          element.placeholder = t(element.dataset.i18nPlaceholder);
        });
        document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
          element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
        });
        document.querySelectorAll("[data-lang]").forEach((button) => {
          const isCurrent = button.dataset.lang === language;
          button.setAttribute("aria-pressed", String(isCurrent));
          // The stylesheet marks the current language with a class; without it
          // the switch kept highlighting Russian after switching to English.
          button.classList.toggle("is-active", isCurrent);
        });
        document.getElementById("task").placeholder = t("taskPlaceholder");
        document.getElementById("operation_name").placeholder = t("operationPlaceholder");
        document.getElementById("department").placeholder = t("departmentPlaceholder");
        document.getElementById("equipment").placeholder = t("equipmentPlaceholder");
        document.getElementById("technical_context").placeholder = t("contextPlaceholder");
        document.getElementById("video_url").placeholder = "https://...";
        fillSelect("user_level", translations[language].levels);
        fillSelect("instruction_type", translations[language].types);
        fillSelect("industry_profile", translations[language].profiles);
        fillWorkflowRoles();
        fillAuthRoles();
        syncAuthControls();
        fillSampleCases();
        syncContextControls();
        syncSelectedFileNames();
        loadDocuments();
        renderResult();
      }

      function syncFilePicker(inputId, nameId) {
        const input = document.getElementById(inputId);
        const name = document.getElementById(nameId);
        const file = input.files && input.files[0];
        name.textContent = file ? file.name : t("noFileSelected");
        name.title = file ? file.name : "";
      }

      function syncSelectedFileNames() {
        syncFilePicker("video_file", "video-file-name");
        syncFilePicker("document_file", "document-file-name");
      }

      function fillSelect(id, labels) {
        const select = document.getElementById(id);
        const currentValue = select.value || optionValues[id][0];
        select.innerHTML = "";
        optionValues[id].forEach((value) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = labels[value];
          select.appendChild(option);
        });
        select.value = currentValue;
      }

      function fillSampleCases() {
        const select = document.getElementById("sample_case");
        const currentValue = select.value || sampleCases[0].id;
        select.innerHTML = "";
        sampleCases.forEach((sample) => {
          const option = document.createElement("option");
          option.value = sample.id;
          option.textContent = sample.labels[language];
          select.appendChild(option);
        });
        select.value = sampleCases.some((sample) => sample.id === currentValue) ? currentValue : sampleCases[0].id;
      }

      function fillWorkflowRoles() {
        const currentValue = workflowReviewerRoleSelect.value || "master";
        workflowReviewerRoleSelect.innerHTML = "";
        reviewerRoleValues.forEach((value) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = translations[language].reviewerRoles[value];
          workflowReviewerRoleSelect.appendChild(option);
        });
        workflowReviewerRoleSelect.value = reviewerRoleValues.includes(currentValue) ? currentValue : "master";
      }

      function fillAuthRoles() {
        const currentValue = authRoleSelect.value || "operator";
        authRoleSelect.innerHTML = "";
        const allowedRoles = userRoleValues.filter((value) =>
          authCapabilities.allowed_registration_roles.includes(value),
        );
        allowedRoles.forEach((value) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = translations[language].userRoles[value];
          authRoleSelect.appendChild(option);
        });
        authRoleSelect.value = allowedRoles.includes(currentValue) ? currentValue : allowedRoles[0] || "operator";
      }

      function applyInstructionPayloadToForm(payload) {
        document.getElementById("task").value = payload.task || "";
        document.getElementById("user_level").value = payload.user_level || "new_operator";
        document.getElementById("instruction_type").value = payload.instruction_type || "general";
        document.getElementById("industry_profile").value = payload.industry_profile || "general";
        document.getElementById("operation_name").value = payload.operation_name || "";
        document.getElementById("department").value = payload.department || "";
        document.getElementById("equipment").value = payload.equipment || "";
        document.getElementById("technical_context").value = payload.technical_context || "";
        document.getElementById("use_context").checked = true;
        syncContextControls();
      }

      function syncContextControls() {
        document.getElementById("max_sources").disabled = !document.getElementById("use_context").checked;
      }

      async function apiFetch(url, options = {}, retryAfterToken = true) {
        const headers = new Headers(options.headers || {});
        const hasAuthenticatedUser = Boolean(currentUser);
        const token = hasAuthenticatedUser ? "" : apiTokenInput.value.trim();
        if (token && !headers.has("Authorization")) {
          headers.set("Authorization", `Bearer ${token}`);
        }
        const method = String(options.method || "GET").toUpperCase();
        if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && !headers.has("X-CSRF-Token")) {
          const csrfToken = cookieValue("industrial_ai_csrf");
          if (csrfToken) {
            headers.set("X-CSRF-Token", csrfToken);
          }
        }
        const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
        if (response.status === 401 && retryAfterToken) {
          if (hasAuthenticatedUser) {
            currentUser = null;
            syncAuthControls();
          }
          const promptedToken = window.prompt(t("authTokenPrompt"), apiTokenInput.value.trim());
          if (promptedToken && promptedToken.trim()) {
            apiTokenInput.value = promptedToken.trim();
            return apiFetch(url, options, false);
          }
        }
        return response;
      }

      function cookieValue(name) {
        const prefix = `${encodeURIComponent(name)}=`;
        const item = document.cookie.split("; ").find((value) => value.startsWith(prefix));
        return item ? decodeURIComponent(item.slice(prefix.length)) : "";
      }

      function syncAuthControls() {
        const roleLabels = translations[language].userRoles || {};
        if (currentUser) {
          authState.textContent = `${currentUser.full_name} · ${roleLabels[currentUser.role] || currentUser.role}`;
          authOpenButton.hidden = true;
          authLogoutButton.hidden = false;
        } else {
          authState.textContent = t("authGuest");
          authOpenButton.hidden = false;
          authLogoutButton.hidden = true;
        }
        const registerOption = authModeSelect.querySelector('option[value="register"]');
        registerOption.hidden = !authCapabilities.public_registration_enabled;
        registerOption.disabled = !authCapabilities.public_registration_enabled;
        if (!authCapabilities.public_registration_enabled && authModeSelect.value === "register") {
          authModeSelect.value = "login";
        }
        const isRegister = authModeSelect.value === "register";
        document.querySelectorAll("[data-auth-register-only]").forEach((element) => {
          element.hidden = !isRegister;
        });
        authFullNameInput.required = isRegister;
        authRoleSelect.disabled = !authCapabilities.role_self_assignment_enabled;
        authPasswordInput.minLength = authCapabilities.minimum_password_length;
        authPasswordInput.autocomplete = isRegister ? "new-password" : "current-password";
      }

      async function loadAuthCapabilities() {
        try {
          const response = await apiFetch("/api/auth/config", {}, false);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          authCapabilities = {
            public_registration_enabled: Boolean(payload.public_registration_enabled),
            role_self_assignment_enabled: Boolean(payload.role_self_assignment_enabled),
            allowed_registration_roles: Array.isArray(payload.allowed_registration_roles)
              ? payload.allowed_registration_roles.filter((role) => userRoleValues.includes(role))
              : ["operator"],
            minimum_password_length: Number(payload.minimum_password_length) || 8,
          };
        } catch (_) {
          // Fail closed: login remains available while unsupported registration controls stay hidden.
        }
        fillAuthRoles();
        syncAuthControls();
      }

      async function loadCurrentUser() {
        try {
          const response = await apiFetch("/api/auth/me", {}, false);
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          const payload = await response.json();
          currentUser = payload.user;
        } catch (error) {
          currentUser = null;
        }
        syncAuthControls();
      }

      function openAuthModal() {
        authModalOpener = document.activeElement;
        authEmailInput.value = "";
        authPasswordInput.value = "";
        authFullNameInput.value = "";
        authModeSelect.value = "login";
        syncAuthControls();
        authModal.hidden = false;
        authEmailInput.focus();
      }

      function closeAuthModal() {
        authModal.hidden = true;
        if (authModalOpener && typeof authModalOpener.focus === "function") {
          authModalOpener.focus();
        }
        authModalOpener = null;
      }

      async function submitAuth(event) {
        event.preventDefault();
        const isRegister = authModeSelect.value === "register";
        const payload = {
          email: authEmailInput.value.trim(),
          password: authPasswordInput.value,
        };
        if (isRegister) {
          payload.full_name = authFullNameInput.value.trim();
          payload.role = authRoleSelect.value;
        }
        status.textContent = t("historyLoading");
        status.classList.remove("error");
        try {
          const response = await apiFetch(isRegister ? "/api/auth/register" : "/api/auth/login", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Auth-Transport": "cookie",
            },
            body: JSON.stringify(payload),
          }, false);
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          const authPayload = await response.json();
          currentUser = authPayload.user;
          closeAuthModal();
          syncAuthControls();
          status.textContent = t("authLoggedIn");
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        }
      }

      async function logoutAuth() {
        if (currentUser) {
          try {
            const response = await apiFetch("/api/auth/logout", { method: "POST" }, false);
            if (!response.ok && response.status !== 401) {
              throw new Error(await responseErrorMessage(response));
            }
          } catch (error) {
            status.textContent = `${t("authLogoutFailed")} ${error.message}`;
            status.classList.add("error");
            return;
          }
        }
        currentUser = null;
        syncAuthControls();
        status.textContent = t("authLoggedOut");
        status.classList.remove("error");
      }

      function resetProcessedVideoState() {
        if (currentVideoJobId) return;
        lastVideoPayload = null;
        videoGenerateButton.disabled = true;
        if (activeTab === "video") {
          renderResult();
        }
      }

      function renderDocumentList(documents) {
        const container = document.getElementById("document-list");
        if (!documents || !documents.length) {
          container.innerHTML = `<div class="step-meta">${t("documentListEmpty")}</div>`;
          return;
        }
        container.innerHTML = `
          <strong>${t("documentListTitle")}</strong>
          ${documents
            .map(
              (documentItem) => `
                <div class="document-item">
                  <strong>${escapeHtml(documentItem.title)}</strong>
                  <div class="step-meta">${escapeHtml(documentItem.original_filename)}</div>
                  <div class="step-meta">${t("documentStoredAs")}: ${escapeHtml(documentItem.stored_filename)}</div>
                  <div class="step-meta">${t("documentCharacters")}: ${escapeHtml(documentItem.extracted_characters)}</div>
                </div>
              `,
            )
            .join("")}
        `;
      }

      async function loadDocuments() {
        try {
          const response = await apiFetch("/api/documents", {}, false);
          if (!response.ok) {
            return;
          }
          const payload = await response.json();
          renderDocumentList(payload.documents || []);
        } catch (error) {
          renderDocumentList([]);
        }
      }

      async function uploadDocument() {
        const input = document.getElementById("document_file");
        const file = input.files && input.files[0];
        if (!file) {
          status.textContent = t("documentStatusNoFile");
          status.classList.add("error");
          return;
        }
        status.textContent = t("documentUploadLoading");
        status.classList.remove("error");
        documentButton.disabled = true;
        try {
          const formData = new FormData();
          formData.append("file", file);
          const response = await apiFetch("/api/documents/upload", {
            method: "POST",
            body: formData,
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          input.value = "";
          syncFilePicker("document_file", "document-file-name");
          document.getElementById("use_context").checked = true;
          syncContextControls();
          await loadDocuments();
          status.textContent = t("documentUploadReady");
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        } finally {
          documentButton.disabled = false;
        }
      }

      function readFormPayload() {
        const formData = new FormData(form);
        const payload = {};
        const useContext = document.getElementById("use_context").checked;
        for (const [key, value] of formData.entries()) {
          if (key === "use_context") {
            continue;
          }
          if (key === "max_sources" && !useContext) {
            continue;
          }
          const trimmed = String(value).trim();
          if (trimmed) {
            payload[key] = key === "max_sources" ? Number(trimmed) : trimmed;
          }
        }
        return payload;
      }

      function optionalSourceRequestPayload() {
        const payload = readFormPayload();
        return payload.task && payload.task.length >= 10 ? payload : null;
      }

      // The stylesheet expects a badge per meaning, never a bare coloured word:
      // risk, provenance and workflow status each map onto a semantic pair.
      const BADGE_VARIANTS = {
        low: "low", medium: "medium", high: "high", critical: "critical",
        confirmed: "confirmed", requires_local_check: "local-check",
        hypothesis: "hypothesis", hypothesis_pending_review: "hypothesis-review",
        draft: "draft", in_review: "review", approved: "approved",
        rejected: "rejected", in_execution: "executing",
        public: "public", local: "local",
      };

      // The bar colour follows the score, so a weak criterion reads as weak
      // without the reader comparing numbers.
      function scoreBand(score) {
        if (score >= 90) return "low";
        if (score >= 75) return "medium";
        if (score >= 50) return "high";
        return "critical";
      }

      function renderBadge(value, label) {
        const variant = BADGE_VARIANTS[value] || "neutral";
        return `<span class="badge badge--${variant}">${escapeHtml(label)}</span>`;
      }

      function renderList(items) {
        const safeItems = items && items.length ? items : [t("noData")];
        return `<ul>${safeItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
      }

      function renderIssueList(items) {
        const safeItems = items && items.length ? items : [t("noIssues")];
        return `<ul>${safeItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
      }

      function responsibilityItems() {
        return language === "ru"
          ? [
              "Оператор выполняет действия только в пределах допуска и фиксирует отклонения.",
              "Мастер смены подтверждает применимость инструкции к конкретному участку и оборудованию.",
              "Инженер/технолог уточняет режимы, допуски и локальные требования, отсутствующие во входных данных.",
            ]
          : [
              "The operator performs only permitted actions and records deviations.",
              "The shift supervisor confirms applicability to the specific area and equipment.",
              "The engineer/technologist verifies modes, tolerances, and local requirements missing from the input.",
            ];
      }

      function acceptanceItems(instruction) {
        const base =
          language === "ru"
            ? [
                "Все обязательные контрольные точки выполнены и подтверждены ответственным лицом.",
                "Рабочее место и оборудование находятся в безопасном, определенном состоянии.",
                "Отклонения, замечания и ограничения зафиксированы в принятой на участке форме.",
              ]
            : [
                "All mandatory control points are completed and confirmed by the responsible person.",
                "The workplace and equipment are in a safe, defined state.",
                "Deviations, remarks, and limits are recorded in the accepted local form.",
              ];
        return [...base, ...(instruction.control_points || [])];
      }

      function renderAuditTrail(events) {
        if (!events || !events.length) {
          return "";
        }
        const eventLabels = translations[language].auditEventTypes || {};
        return `
          <section>
            <h3>${t("auditTrailTitle")}</h3>
            ${events
              .map((event) => {
                const metadataEntries = Object.entries(event.metadata || {});
                const transition =
                  event.from_status || event.to_status
                    ? `<p class="step-meta">${t("auditEventTransition")}: ${escapeHtml(event.from_status || t("noData"))} -&gt; ${escapeHtml(event.to_status || t("noData"))}</p>`
                    : "";
                const metadata = metadataEntries.length
                  ? `<p class="step-meta">${t("auditEventMetadata")}: ${escapeHtml(metadataEntries.map(([key, value]) => `${key}=${value}`).join(", "))}</p>`
                  : "";
                return `
                  <div class="source-card">
                    <h3>${escapeHtml(eventLabels[event.event_type] || event.event_type)}</h3>
                    <p class="step-meta">${t("auditEventCreated")}: ${escapeHtml(formatDateTime(event.created_at))}</p>
                    <p class="step-meta">${t("auditEventActor")}: ${escapeHtml(event.actor || t("noData"))}</p>
                    ${
                      event.reviewer_role
                        ? `<p class="step-meta">${t("workflowReviewerRole")}: ${escapeHtml(translations[language].reviewerRoles[event.reviewer_role] || event.reviewer_role)}</p>`
                        : ""
                    }
                    ${transition}
                    ${event.comment ? `<p class="step-meta">${t("auditEventComment")}: ${escapeHtml(event.comment)}</p>` : ""}
                    ${metadata}
                  </div>
                `;
              })
              .join("")}
          </section>
        `;
      }

      function implementationLimitItems() {
        return language === "ru"
          ? [
              "Документ является AI-черновиком и не заменяет утвержденные инструкции предприятия.",
              "Точные режимы, нормы времени, допуски и ссылки на стандарты должны быть подтверждены локальной документацией.",
              "Перед применением на производстве инструкцию должен проверить ответственный специалист по технологии и охране труда.",
            ]
          : [
              "This document is an AI draft and does not replace approved company instructions.",
              "Exact modes, time norms, tolerances, and standard references must be verified against local documentation.",
              "Before production use, the instruction must be reviewed by the responsible technology and safety specialist.",
            ];
      }

      function formatTimestamp(seconds) {
        const totalSeconds = Math.round(Number(seconds) || 0);
        const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
        const remainder = String(totalSeconds % 60).padStart(2, "0");
        return `${minutes}:${remainder}`;
      }

      function renderStepFrameLink(link) {
        if (!link) {
          return "";
        }
        const image = link.image_url
          ? protectedImageMarkup(link.image_url, `${t("frame")} ${link.frame_index}`)
          : "";
        return `
          <div class="step-video-link">
            ${image}
            <div>
              <strong>${t("stepFrameLink")}: ${t("frame")} ${escapeHtml(link.frame_index)} · ${formatTimestamp(link.timestamp_seconds)}</strong>
              <div class="step-meta">${t("linkReason")}: ${escapeHtml(link.reason)}</div>
              <div class="step-meta">${t("confidence")}: ${escapeHtml(link.confidence)}</div>
            </div>
          </div>
        `;
      }

      const editorListFields = [
        "required_ppe",
        "required_tools",
        "safety_requirements",
        "hazard_zones",
        "prerequisites",
        "control_points",
        "quality_checklist",
        "emergency_actions",
        "common_mistakes",
        "observed_facts",
        "local_verification_required",
        "expert_review_questions",
      ];

      const requiredEditorListFields = new Set([
        "required_ppe",
        "required_tools",
        "safety_requirements",
        "hazard_zones",
        "prerequisites",
        "control_points",
        "quality_checklist",
        "emergency_actions",
        "common_mistakes",
      ]);

      function listToText(items) {
        return (items || []).join("\n");
      }

      function textToList(value, fallbackRequired = false) {
        const items = String(value || "")
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean);
        if (!items.length && fallbackRequired) {
          return [t("noData")];
        }
        return items;
      }

      function editorTextarea(field, label, value, required = false) {
        return `
          <div class="field">
            <label for="editor_${field}">${label}</label>
            <textarea id="editor_${field}" data-editor-list="${field}" ${required ? "required" : ""} placeholder="${t("editorListHint")}">${escapeHtml(listToText(value))}</textarea>
          </div>
        `;
      }

      function renderEditor(payload) {
        const instruction = payload.instruction;
        return `
          <div class="editor-form">
            <section class="editor-section">
              <h3>${t("editorTitle")}</h3>
              <p class="step-meta">${t("editorListHint")}</p>
              <div class="editor-actions">
                <button class="secondary-action" type="button" data-editor-action="apply">${t("editorApply")}</button>
                <button class="secondary-action" type="button" data-editor-action="improve">${t("editorImprove")}</button>
              </div>
            </section>
            <section class="editor-section">
              <h3>${t("editorMainFields")}</h3>
              <div class="field"><label for="editor_title">${t("instructionTitle")}</label><input id="editor_title" data-editor-field="title" value="${escapeHtml(instruction.title)}" required /></div>
              <div class="field"><label for="editor_purpose">${t("purpose")}</label><textarea id="editor_purpose" data-editor-field="purpose" required>${escapeHtml(instruction.purpose)}</textarea></div>
              <div class="field"><label for="editor_scope">${t("scope")}</label><textarea id="editor_scope" data-editor-field="scope" required>${escapeHtml(instruction.scope)}</textarea></div>
              <div class="grid-2">
                <div class="field"><label for="editor_department">${t("department")}</label><input id="editor_department" data-editor-field="department" value="${escapeHtml(instruction.department || "")}" /></div>
                <div class="field"><label for="editor_equipment">${t("equipment")}</label><input id="editor_equipment" data-editor-field="equipment" value="${escapeHtml(instruction.equipment || "")}" /></div>
              </div>
              <div class="field"><label for="editor_operator_level">${t("operatorLevel")}</label><input id="editor_operator_level" data-editor-field="operator_level" value="${escapeHtml(instruction.operator_level)}" required /></div>
            </section>
            <section class="editor-section">
              <h3>${t("editorSafetyFields")}</h3>
              ${editorTextarea("required_ppe", t("ppe"), instruction.required_ppe, true)}
              ${editorTextarea("required_tools", t("tools"), instruction.required_tools, true)}
              ${editorTextarea("safety_requirements", t("safety"), instruction.safety_requirements, true)}
              ${editorTextarea("hazard_zones", t("hazards"), instruction.hazard_zones, true)}
              ${editorTextarea("prerequisites", t("prerequisites"), instruction.prerequisites, true)}
            </section>
            <section class="editor-section">
              <h3>${t("editorSteps")}</h3>
              ${(instruction.steps || [])
                .map(
                  (step, index) => `
                    <div class="editor-step" data-editor-step="${index}">
                      <strong>${escapeHtml(step.number)}. ${escapeHtml(step.action)}</strong>
                      <div class="field"><label>${t("steps")}</label><textarea data-step-field="action" required>${escapeHtml(step.action)}</textarea></div>
                      <div class="field"><label>${t("expectedResult")}</label><textarea data-step-field="expected_result" required>${escapeHtml(step.expected_result)}</textarea></div>
                      <div class="field"><label>${t("safetyNote")}</label><textarea data-step-field="safety_note">${escapeHtml(step.safety_note || "")}</textarea></div>
                      <div class="field"><label>${t("verification")}</label><textarea data-step-field="verification_method">${escapeHtml(step.verification_method || "")}</textarea></div>
                      <div class="field"><label>${t("commonMistakes")}</label><textarea data-step-field="common_mistakes" placeholder="${t("editorListHint")}">${escapeHtml(listToText(step.common_mistakes))}</textarea></div>
                    </div>
                  `,
                )
                .join("")}
            </section>
            <section class="editor-section">
              <h3>${t("editorReviewFields")}</h3>
              ${editorTextarea("control_points", t("controlPoints"), instruction.control_points, true)}
              ${editorTextarea("quality_checklist", t("qualityChecklist"), instruction.quality_checklist, true)}
              ${editorTextarea("emergency_actions", t("emergencyActions"), instruction.emergency_actions, true)}
              ${editorTextarea("common_mistakes", t("commonMistakes"), instruction.common_mistakes, true)}
              ${editorTextarea("observed_facts", t("observedFacts"), instruction.observed_facts)}
              ${editorTextarea("local_verification_required", t("localVerificationRequired"), instruction.local_verification_required)}
              ${editorTextarea("expert_review_questions", t("expertReviewQuestions"), instruction.expert_review_questions)}
            </section>
          </div>
        `;
      }

      function renderExecution(payload) {
        const instruction = payload.instruction;
        const steps = instruction.steps || [];
        const qualityItems = acceptanceItems(instruction);
        const canSaveExecution = Boolean(currentHistoryRecord);
        return `
          <div class="instruction execution-view ${shopFloorMode ? "shop-floor-mode" : ""}">
            <section>
              <h3>${t("executionTitle")}</h3>
              <p class="step-meta">${t("executionMeta")}</p>
              <p class="step-meta">${t("workflowStatus")}: ${escapeHtml((instruction.workflow || {}).status_label || t("noData"))}</p>
              ${canSaveExecution ? "" : `<p class="step-meta">${t("executionSaveUnavailable")}</p>`}
              <label class="checkbox-field">
                <input type="checkbox" data-execution-action="toggle-shop-floor" ${shopFloorMode ? "checked" : ""} />
                <span>${t("shopFloorMode")}</span>
              </label>
              <p class="step-meta">${t("shopFloorModeHint")}</p>
              <div class="field">
                <label for="execution_executor">${t("executionExecutor")}</label>
                <input id="execution_executor" placeholder="${t("executionExecutorPlaceholder")}" />
              </div>
            </section>
            <section>
              <h3>${t("executionSteps")}</h3>
              <div class="execution-list">
                ${steps
                  .map(
                    (step) => `
                      <label class="execution-item">
                        <input type="checkbox" data-execution-kind="step" data-execution-label="${escapeHtml(`${step.number}. ${step.action}`)}" />
                        <span>
                          <strong>${escapeHtml(step.number)}. ${escapeHtml(step.action)}</strong>
                          <span class="step-meta">${t("expectedResult")}: ${escapeHtml(step.expected_result)}</span>
                          ${step.safety_note ? `<span class="step-meta">${t("safetyNote")}: ${escapeHtml(step.safety_note)}</span>` : ""}
                        </span>
                      </label>
                    `,
                  )
                  .join("")}
              </div>
            </section>
            <section>
              <h3>${t("executionQuality")}</h3>
              <div class="execution-list">
                ${qualityItems
                  .map(
                    (item) => `
                      <label class="execution-item">
                        <input type="checkbox" data-execution-kind="quality" data-execution-label="${escapeHtml(item)}" />
                        <span>${escapeHtml(item)}</span>
                      </label>
                    `,
                  )
                  .join("")}
              </div>
            </section>
            <section>
              <h3>${t("executionNotes")}</h3>
              <textarea id="execution_notes" placeholder="${t("executionNotesPlaceholder")}"></textarea>
              <button class="secondary-action" type="button" data-execution-action="save" ${canSaveExecution ? "" : "disabled"}>${t("executionSave")}</button>
            </section>
          </div>
        `;
      }

      function renderInstruction(payload) {
        const instruction = payload.instruction;
        const workflow = instruction.workflow || {};
        const linksByStep = new Map((payload.step_frame_links || []).map((link) => [link.step_number, link]));
        return `
          <div class="instruction">
            <div class="doc-head">
              <div class="doc-meta">
                ${workflow.status ? renderBadge(workflow.status, workflow.status_label || workflow.status) : ""}
                ${payload.evaluation && payload.evaluation.risk_level
                  ? renderBadge(
                      payload.evaluation.risk_level,
                      `${t("riskLevel")}: ${translations[language].riskLabels[payload.evaluation.risk_level] || payload.evaluation.risk_level}`,
                    )
                  : ""}
                <span class="doc-meta-text">${escapeHtml(generationModeLabel(payload.generation_mode))}</span>
              </div>
              <h3 class="doc-title">${escapeHtml(instruction.title)}</h3>
              <p class="doc-lede">${escapeHtml(instruction.purpose)}</p>
              <p class="doc-lede">${escapeHtml(instruction.scope)}</p>
            </div>
            <section>
              <h3>${t("passport")}</h3>
              <ul>
                <li>${t("department")}: ${escapeHtml(instruction.department || t("noData"))}</li>
                <li>${t("equipment")}: ${escapeHtml(instruction.equipment || t("noData"))}</li>
                <li>${t("operatorLevel")}: ${escapeHtml(instruction.operator_level)}</li>
                <li>${t("workflowStatus")}: ${escapeHtml(workflow.status_label || t("noData"))}</li>
              </ul>
            </section>
            <section><h3>${t("approvalRoles")}</h3>${renderList(workflow.required_review_roles)}</section>
            <section><h3>${t("approvalBlockers")}</h3>${renderList(workflow.approval_blockers)}</section>
            <section><h3>${t("workflowNextActions")}</h3>${renderList(workflow.next_actions)}</section>
            <section><h3>${t("ppe")}</h3>${renderList(instruction.required_ppe)}</section>
            <section><h3>${t("responsibilityMatrix")}</h3>${renderList(responsibilityItems())}</section>
            <section><h3>${t("observedFacts")}</h3>${renderList(instruction.observed_facts)}</section>
            <section><h3>${t("evidenceProvenance")}</h3>${renderList(
              (instruction.evidence_claims || []).map(
                (claim) => {
                  const record = claim.validation_record;
                  const validation = record
                    ? ` · ${record.reviewer_name} (${record.reviewer_role}) · ${record.evidence_reference}`
                    : "";
                  return `[${claim.claim_id || "no-claim-id"}; ${claim.provenance}; ${claim.validation_status}; source=${claim.source_id || "none"}] ${claim.text}${validation}`;
                },
              ),
            )}</section>
            <section><h3>${t("localVerificationRequired")}</h3>${renderList(instruction.local_verification_required)}</section>
            <section><h3>${t("expertReviewQuestions")}</h3>${renderList(instruction.expert_review_questions)}</section>
            <section><h3>${t("tools")}</h3>${renderList(instruction.required_tools)}</section>
            <section><h3>${t("safety")}</h3>${renderList(instruction.safety_requirements)}</section>
            <section><h3>${t("hazards")}</h3>${renderList(instruction.hazard_zones)}</section>
            <section><h3>${t("prerequisites")}</h3>${renderList(instruction.prerequisites)}</section>
            <section>
              <h3>${t("steps")}</h3>
              <div class="steps">
                ${instruction.steps
                  .map(
                    (step) => `
                      <div class="step">
                        <div class="step-index">${step.number}</div>
                        <div class="step-body">
                          <p class="step-action">${escapeHtml(step.action)}</p>
                          <dl class="step-meta">
                            <dt>${t("expectedResult")}</dt>
                            <dd>${escapeHtml(step.expected_result)}</dd>
                            ${
                              step.verification_method
                                ? `<dt>${t("verification")}</dt><dd>${escapeHtml(step.verification_method)}</dd>`
                                : ""
                            }
                            ${
                              step.common_mistakes && step.common_mistakes.length
                                ? `<dt>${t("commonMistakes")}</dt><dd>${escapeHtml(step.common_mistakes.join(", "))}</dd>`
                                : ""
                            }
                          </dl>
                          ${
                            step.safety_note
                              ? `<p class="safety-note">${t("safetyNote")}: ${escapeHtml(step.safety_note)}</p>`
                              : ""
                          }
                          ${renderStepFrameLink(linksByStep.get(step.number))}
                        </div>
                      </div>
                    `,
                  )
                  .join("")}
              </div>
            </section>
            <section><h3>${t("acceptanceCriteria")}</h3>${renderList(acceptanceItems(instruction))}</section>
            <section><h3>${t("controlPoints")}</h3>${renderList(instruction.control_points)}</section>
            <section><h3>${t("qualityChecklist")}</h3>${renderList(instruction.quality_checklist)}</section>
            <section><h3>${t("emergencyActions")}</h3>${renderList(instruction.emergency_actions)}</section>
            <section><h3>${t("commonMistakes")}</h3>${renderList(instruction.common_mistakes)}</section>
            <section><h3>${t("implementationLimits")}</h3>${renderList(implementationLimitItems())}</section>
            ${renderAuditTrail(currentAuditEvents)}
          </div>
        `;
      }

      function renderEvaluation(payload) {
        const evaluation = payload.evaluation;
        if (!evaluation) {
          return `<div class="empty-state"><p class="empty-title">${t("noData")}</p></div>`;
        }
        return `
          <div class="instruction">
            <section class="score-summary">
              <div class="score-value">${evaluation.overall_score}</div>
              <div class="score-caption">${t("overallScore")}</div>
              ${renderBadge(
                evaluation.risk_level,
                `${t("riskLevel")}: ${translations[language].riskLabels[evaluation.risk_level] || evaluation.risk_level || t("noData")}`,
              )}
            </section>
            <section>
              <p class="doc-lede">${escapeHtml(evaluation.verdict)}</p>
              <p class="criterion-note">${t("regulatoryBasis")}</p>
              ${
                (evaluation.regulatory_sources || []).length
                  ? `<p class="criterion-note">${t("regulatorySources")}: ${escapeHtml((evaluation.regulatory_sources || []).join("; "))}</p>`
                  : ""
              }
              <p class="criterion-note">${t("expertReview")}: ${
                evaluation.expert_review_required ? t("expertReviewRequired") : t("expertReviewOptional")
              }</p>
            </section>
            <section><h3>${t("expertReview")}</h3>${renderList(evaluation.expert_review_notes)}</section>
            <section><h3>${t("safetyFindings")}</h3>${renderList(
              (evaluation.safety_findings || []).map(
                (finding) => `[${finding.severity}; ${finding.code}] ${finding.message}`,
              ),
            )}</section>
            <section>
              <h3>${t("criteria")}</h3>
              <div class="criteria">
                ${evaluation.criteria
                  .map(
                    (criterion) => `
                      <div class="criterion criterion--${scoreBand(criterion.score)}">
                        <div>
                          <div class="criterion-head">
                            <span class="criterion-name">${escapeHtml(translations[language].criterionLabels[criterion.criterion] || criterion.label)}</span>
                          </div>
                          <div class="criterion-note">${t("strengths")}:</div>
                          ${renderList(criterion.strengths)}
                          <div class="criterion-note">${t("issues")}:</div>
                          ${renderIssueList(criterion.issues)}
                        </div>
                        <div class="criterion-score-cell">
                          <div class="criterion-score">${criterion.score}</div>
                          <div class="criterion-bar">
                            <div class="criterion-bar-fill" data-bar-value="${criterion.score}"></div>
                          </div>
                        </div>
                      </div>
                    `,
                  )
                  .join("")}
              </div>
            </section>
            <section><h3>${t("missingElements")}</h3>${renderList(evaluation.missing_elements)}</section>
            <section><h3>${t("recommendations")}</h3>${renderList(evaluation.recommendations)}</section>
          </div>
        `;
      }

      function renderSources(payload) {
        const sources = payload.sources || [];
        if (!sources.length) {
          return `<div class="empty-state"><p class="empty-title">${t("noSources")}</p></div>`;
        }
        return `
          <div class="instruction">
            <section>
              <h3>${t("sourceTitle")}</h3>
              <p class="step-meta">${t("sourceExplanation")}</p>
              <div class="sources">
              ${sources
                .map(
                  (source) => `
                    <div class="source">
                      <div class="source-head">
                        ${renderBadge(
                          source.source_type,
                          source.source_type === "public" ? t("sourceTypePublic") : t("sourceTypeLocal"),
                        )}
                        ${source.document_type ? `<span class="source-kind">${escapeHtml(source.document_type)}</span>` : ""}
                      </div>
                      <h3 class="source-title">${escapeHtml(source.title)}</h3>
                      ${source.authority ? `<p class="step-meta">${t("sourceAuthority")}: ${escapeHtml(source.authority)}</p>` : ""}
                      <p class="step-meta">${t("sourceScore")}: ${escapeHtml(source.score)}</p>
                      <p class="step-meta">${t("sourceInfluence")}: ${escapeHtml(formatPercent(source.influence_score || 0))}</p>
                      ${
                        source.applicable_profiles && source.applicable_profiles.length
                          ? `<p class="step-meta">${t("sourceProfiles")}: ${escapeHtml(formatProfiles(source.applicable_profiles))}</p>`
                          : ""
                      }
                      ${source.contribution_reason ? `<p class="source-reason">${escapeHtml(source.contribution_reason)}</p>` : ""}
                      ${
                        source.matched_terms && source.matched_terms.length
                          ? `<p class="step-meta">${t("matchedTerms")}: ${escapeHtml(source.matched_terms.join(", "))}</p>`
                          : ""
                      }
                      ${
                        source.url
                          ? `<p class="step-meta">${t("sourceUrl")}: <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.url)}</a></p>`
                          : `<p class="step-meta">${t("sourcePath")}: ${escapeHtml(source.path)} #${escapeHtml(source.chunk_index)}</p>`
                      }
                      <p>${escapeHtml(source.excerpt)}</p>
                    </div>
                  `,
                )
                .join("")}
              </div>
            </section>
          </div>
        `;
      }

      function renderVideo() {
        const video = lastVideoPayload;
        if (!video) {
          return `<div class="empty-state"><p class="empty-title">${t("noVideo")}</p></div>`;
        }
        return `
          <div class="instruction">
            <section>
              <h3>${t("videoMeta")}</h3>
              <ul>
                <li>${t("videoSource")}: ${escapeHtml(video.original_filename)}</li>
                <li>FPS: ${escapeHtml(video.fps)}</li>
                <li>${t("videoDuration")}: ${escapeHtml(video.duration_seconds)}s</li>
                <li>${t("videoTotalFrames")}: ${escapeHtml(video.frame_count)}</li>
                <li>${t("videoVisualQuality")}: ${escapeHtml(video.visual_quality || t("noData"))}</li>
              </ul>
            </section>
            ${
              video.extracted_context
                ? `<section><h3>${t("videoContextTitle")}</h3><pre>${escapeHtml(video.extracted_context)}</pre></section>`
                : ""
            }
            ${renderVideoSegments(video.video_segments || [])}
            ${renderFrameAnalyses(video.frame_analyses || [])}
            <section>
              <h3>${t("videoTitle")}</h3>
              ${
                video.keyframes && video.keyframes.length
                  ? `<div class="keyframe-grid">
                      ${video.keyframes
                        .map(
                          (keyframe) => `
                            <div class="keyframe-card">
                              ${protectedImageMarkup(keyframe.image_url, `${t("frame")} ${keyframe.frame_index}`)}
                              <div>
                                <strong>${t("frame")} ${escapeHtml(keyframe.frame_index)}</strong>
                                <p class="step-meta">${t("timestamp")}: ${escapeHtml(keyframe.timestamp_seconds)}s</p>
                                <p class="step-meta">${t("frameSelectionScore")}: ${escapeHtml(keyframe.selection_score || 0)}</p>
                                ${
                                  keyframe.selection_reason
                                    ? `<p class="step-meta">${t("frameSelectionReason")}: ${escapeHtml(keyframe.selection_reason)}</p>`
                                    : ""
                                }
                              </div>
                            </div>
                          `,
                        )
                        .join("")}
                    </div>`
                  : `<p>${t("noData")}</p>`
              }
            </section>
            ${video.notes && video.notes.length ? `<section><h3>${t("videoNotes")}</h3>${renderList(video.notes)}</section>` : ""}
          </div>
        `;
      }

      function renderFrameAnalyses(analyses) {
        if (!analyses.length) {
          return "";
        }
        return `
          <section>
            <h3>${t("frameAnalysisTitle")}</h3>
            ${analyses
              .map(
                (analysis) => `
                  <div class="source-card">
                    <h3>${t("frame")} ${escapeHtml(analysis.frame_index)} · ${escapeHtml(analysis.timestamp_seconds)}s</h3>
                    <p>${escapeHtml(analysis.summary)}</p>
                    <p class="step-meta">${t("frameAnalysisMode")}: ${escapeHtml(analysis.analysis_mode)}</p>
                    <div class="step-meta">${t("visibleEquipment")}:</div>${renderList(analysis.visible_equipment)}
                    <div class="step-meta">${t("operatorActions")}:</div>${renderList(analysis.operator_actions)}
                    <div class="step-meta">${t("safetyObservations")}:</div>${renderList(analysis.safety_observations)}
                    <div class="step-meta">${t("ppeObservations")}:</div>${renderList(analysis.ppe_observations)}
                    <div class="step-meta">${t("potentialHazards")}:</div>${renderList(analysis.potential_hazards)}
                    <div class="step-meta">${t("uncertainties")}:</div>${renderList(analysis.uncertainties)}
                  </div>
                `,
              )
              .join("")}
          </section>
        `;
      }

      function renderVideoSegments(segments) {
        if (!segments.length) {
          return "";
        }
        return `
          <section>
            <h3>${t("videoSegmentsTitle")}</h3>
            ${segments
              .map(
                (segment) => `
                  <div class="source-card">
                    <h3>${t("videoSegment")} ${escapeHtml(segment.segment_index)} · ${escapeHtml(segment.start_seconds)}-${escapeHtml(segment.end_seconds)}s</h3>
                    <p>${escapeHtml(segment.summary)}</p>
                    <p class="step-meta">${t("videoSegmentFrames")}: ${escapeHtml((segment.frame_indices || []).join(", ") || t("noData"))}</p>
                    <div class="step-meta">${t("videoSegmentActions")}:</div>${renderList(segment.dominant_actions)}
                    <div class="step-meta">${t("videoSegmentEquipment")}:</div>${renderList(segment.visible_equipment)}
                    <div class="step-meta">${t("videoSegmentSafety")}:</div>${renderList(segment.safety_findings)}
                    <div class="step-meta">${t("uncertainties")}:</div>${renderList(segment.uncertainties)}
                  </div>
                `,
              )
              .join("")}
          </section>
        `;
      }

      // Bar widths travel as a data attribute and become a custom property here.
      // Writing them as a style attribute would be refused by the CSP.
      function applyBarValues() {
        result.querySelectorAll("[data-bar-value]").forEach((bar) => {
          bar.style.setProperty("--bar-value", `${bar.dataset.barValue}%`);
        });
      }

      function renderResult() {
        revokeProtectedImageUrls();
        syncExportButtons();
        if (activeTab === "video") {
          result.innerHTML = renderVideo();
          hydrateProtectedImages();
          return;
        }
        if (activeTab === "history") {
          result.innerHTML = renderHistory();
          return;
        }
        if (!lastPayload) {
          result.innerHTML = `
            <div class="empty-state">
              <p class="empty-title">${t("emptyTitle")}</p>
              <p class="empty-text">${t("emptyBody")}</p>
            </div>
          `;
          return;
        }

        if (activeTab === "instruction") {
          result.innerHTML = renderInstruction(lastPayload);
        } else if (activeTab === "editor") {
          result.innerHTML = renderEditor(lastPayload);
        } else if (activeTab === "execution") {
          result.innerHTML = renderExecution(lastPayload);
        } else if (activeTab === "evaluation") {
          result.innerHTML = renderEvaluation(lastPayload);
        } else if (activeTab === "sources") {
          result.innerHTML = renderSources(lastPayload);
        } else if (activeTab === "markdown") {
          result.innerHTML = `<pre class="code-view">${escapeHtml(lastPayload.markdown)}</pre>`;
        } else {
          result.innerHTML = `<pre class="code-view">${escapeHtml(JSON.stringify(lastPayload, null, 2))}</pre>`;
        }
        applyBarValues();
        hydrateProtectedImages();
      }

      function syncTabState() {
        const activeButton = tabButtons.find((button) => button.dataset.resultView === activeTab);
        if (activeButton) {
          result.setAttribute("aria-labelledby", activeButton.id);
        }
        syncSidebarState(activeTab);
      }

      function focusableModalElements(modal) {
        return Array.from(
          modal.querySelectorAll("button, input, select, textarea, [href], [tabindex]:not([tabindex='-1'])"),
        ).filter((element) => !element.disabled && element.getClientRects().length > 0);
      }

      function handleModalKeydown(event, modal, closeModal) {
        if (event.key === "Escape") {
          event.preventDefault();
          closeModal();
          return;
        }
        if (event.key !== "Tab") return;
        const focusable = focusableModalElements(modal);
        if (!focusable.length) {
          event.preventDefault();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }

      const protectedImageUrls = new Set();

      function protectedImageMarkup(url, alt) {
        return `<img data-protected-src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" />`;
      }

      function revokeProtectedImageUrls() {
        protectedImageUrls.forEach((url) => URL.revokeObjectURL(url));
        protectedImageUrls.clear();
      }

      async function hydrateProtectedImages() {
        const images = Array.from(result.querySelectorAll("img[data-protected-src]"));
        await Promise.all(
          images.map(async (image) => {
            try {
              const response = await apiFetch(image.dataset.protectedSrc, {}, false);
              if (!response.ok) {
                return;
              }
              const objectUrl = URL.createObjectURL(await response.blob());
              protectedImageUrls.add(objectUrl);
              image.src = objectUrl;
            } catch (error) {
              console.warn("Unable to load protected keyframe", error);
            }
          }),
        );
      }

      function syncExportButtons() {
        const disabled = !lastPayload;
        exportMarkdownButton.disabled = disabled;
        exportPdfButton.disabled = disabled;
        exportJsonButton.disabled = disabled;
        saveHistoryButton.disabled = disabled;
        improveInstructionButton.disabled = disabled;
        syncRouteStepper();
      }

      // Order of the approval route, used to mark what is behind and where the
      // document stands now.
      const ROUTE_SEQUENCE = ["ai_draft", "expert_review", "approved"];

      function syncRouteStepper() {
        const stepper = document.querySelector(".route-stepper");
        if (!stepper) return;
        const steps = Array.from(stepper.querySelectorAll(".route-step"));
        // With no document there is no route: showing "in review" on an empty
        // screen claims a status the product has not given anything yet.
        stepper.hidden = !lastPayload;
        if (!lastPayload) return;
        const status = (lastPayload.instruction.workflow || {}).status;
        const current = ROUTE_SEQUENCE.indexOf(status);
        steps.forEach((step, index) => {
          step.classList.toggle("is-done", current >= 0 && index < current);
          step.classList.toggle("is-current", index === current);
        });
      }

      function downloadTextFile(filename, content, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      }

      function resultFilename(extension) {
        const title = lastPayload && lastPayload.instruction ? lastPayload.instruction.title : "instruction";
        const slug = title
          .toLowerCase()
          .replace(/[^a-zа-яё0-9]+/gi, "-")
          .replace(/^-+|-+$/g, "")
          .slice(0, 60);
        return `${slug || "instruction"}.${extension}`;
      }

      async function downloadPdfFile() {
        if (!lastPayload) {
          return;
        }
        exportPdfButton.disabled = true;
        try {
          const response = await apiFetch("/api/instructions/export-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(lastPayload),
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = resultFilename("pdf");
          document.body.appendChild(link);
          link.click();
          link.remove();
          URL.revokeObjectURL(url);
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        } finally {
          exportPdfButton.disabled = !lastPayload;
        }
      }

      function buildVideoInstructionPayload(video) {
        const title = video.original_filename || "Видео производственной операции";
        const keyframeContext = (video.keyframes || [])
          .map((keyframe) =>
            [
              `Ключевой кадр: ${keyframe.timestamp_seconds}s, индекс ${keyframe.frame_index}.`,
              `Оценка информативности: ${keyframe.selection_score || 0}.`,
              keyframe.selection_reason ? `Причина выбора: ${keyframe.selection_reason}.` : "",
            ]
              .filter(Boolean)
              .join(" "),
          )
          .join("\n");
        const frameAnalysisContext = (video.frame_analyses || [])
          .map(
            (analysis) =>
              [
                `Анализ кадра ${analysis.frame_index} (${analysis.timestamp_seconds}s): ${analysis.summary}`,
                `Оборудование/объекты: ${(analysis.visible_equipment || []).join(", ") || "не выявлено"}`,
                `Действия оператора: ${(analysis.operator_actions || []).join(", ") || "не выявлено"}`,
                `Безопасность: ${(analysis.safety_observations || []).join(", ") || "не выявлено"}`,
                `СИЗ: ${(analysis.ppe_observations || []).join(", ") || "не выявлено"}`,
                `Потенциальные опасности: ${(analysis.potential_hazards || []).join(", ") || "не выявлено"}`,
              ].join("\n"),
          )
          .join("\n\n");
        const segmentContext = (video.video_segments || [])
          .map(
            (segment) =>
              [
                `Этап видео ${segment.segment_index}: ${segment.start_seconds}-${segment.end_seconds}s, кадры ${(segment.frame_indices || []).join(", ")}.`,
                `Кратко: ${segment.summary}`,
                `Действия этапа: ${(segment.dominant_actions || []).join(", ") || "не выявлено"}`,
                `Оборудование/объекты этапа: ${(segment.visible_equipment || []).join(", ") || "не выявлено"}`,
                `Риски/безопасность этапа: ${(segment.safety_findings || []).join(", ") || "не выявлено"}`,
                `Неопределенности этапа: ${(segment.uncertainties || []).join(", ") || "не выявлено"}`,
              ].join("\n"),
          )
          .join("\n\n");
        const hasFrameAnalysisInContext = (video.extracted_context || "").includes("Анализ ключевых кадров:");
        const hasSegmentContext = (video.extracted_context || "").includes("Смысловые этапы видео:");
        const technicalContext = compactVideoContext([
          video.extracted_context || "",
          segmentContext && !hasSegmentContext ? `Смысловые этапы видео:\n${segmentContext}` : "",
          frameAnalysisContext && !hasFrameAnalysisInContext ? `Визуальный анализ ключевых кадров:\n${frameAnalysisContext}` : "",
          keyframeContext ? `Таймкоды ключевых кадров:\n${keyframeContext}` : "",
          !video.extracted_context && !video.transcript
            ? "Текстовый контекст из видео не найден: инструкция основана только на имени файла и таймкодах ключевых кадров."
            : "",
          "Составить инструкцию только как черновик: неизвестные точные режимы, допуски и локальные требования отметить как требующие проверки на месте.",
        ]
          .filter(Boolean)
          .join("\n\n"));
        return {
          task: `Составить производственную инструкцию на основе видео: ${title}`,
          user_level: document.getElementById("user_level").value || "new_operator",
          instruction_type: inferInstructionType(`${title}\n${technicalContext}`),
          industry_profile: document.getElementById("industry_profile").value || "general",
          operation_name: title,
          technical_context: technicalContext,
          max_sources: Number(document.getElementById("max_sources").value || 15),
        };
      }

      function compactVideoContext(context) {
        const limit = 12000;
        if (!context || context.length <= limit) {
          return context;
        }
        const marker =
          "\n\n[Контекст видео автоматически сокращен: сохранены начало и финальные фрагменты. Полный транскрипт нужно проверять отдельно при внедрении.]\n\n";
        const head = context.slice(0, 8000).trimEnd();
        const tail = context.slice(-(limit - head.length - marker.length)).trimStart();
        return `${head}${marker}${tail}`;
      }

      function applyVideoPayloadToForm(payload) {
        document.getElementById("task").value = payload.task;
        document.getElementById("operation_name").value = payload.operation_name || "";
        document.getElementById("technical_context").value = payload.technical_context || "";
        document.getElementById("instruction_type").value = payload.instruction_type;
        document.getElementById("industry_profile").value = payload.industry_profile || "general";
        document.getElementById("max_sources").value = String(payload.max_sources || 15);
        document.getElementById("use_context").checked = true;
        syncContextControls();
      }

      function inferInstructionType(text) {
        const lower = text.toLowerCase();
        if (lower.includes("обуч") || lower.includes("инструктаж")) {
          return "training";
        }
        if (lower.includes("подготов")) {
          return "workplace_preparation";
        }
        if (lower.includes("останов") || lower.includes("передач")) {
          return "equipment_shutdown";
        }
        if (lower.includes("запуск")) {
          return "equipment_startup";
        }
        if (lower.includes("обслуж") || lower.includes("ремонт")) {
          return "maintenance";
        }
        if (lower.includes("контрол") || lower.includes("провер")) {
          return "inspection";
        }
        return document.getElementById("instruction_type").value || "general";
      }

      function generationModeLabel(mode) {
        // The stored value is deliberately vendor-neutral; the screen should say
        // what it means rather than echo an internal identifier.
        const labels = translations[language].generationModeLabels || {};
        return labels[mode] || mode || "";
      }

      function escapeHtml(value) {
        return String(value)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      function formatPercent(value) {
        return `${Math.round((Number(value) || 0) * 100)}%`;
      }

      function formatProfiles(profiles) {
        return (profiles || []).map((profile) => translations[language].profiles[profile] || profile).join(", ");
      }

      function formatDateTime(value) {
        if (!value) {
          return t("noData");
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
          return value;
        }
        return date.toLocaleString(language === "ru" ? "ru-RU" : "en-US");
      }

      function renderHistory() {
        if (!historyRecords.length) {
          return `<div class="empty-state"><p class="empty-title">${t("historyEmpty")}</p></div>`;
        }
        const renderExecutionSummary = () => {
          if (!executionSummary || !executionSummary.total_runs) {
            return "";
          }
          return `
            <section>
              <h3>${t("executionSummaryTitle")}</h3>
              <div class="criteria-grid">
                <div class="criterion-card"><div class="criterion-head"><span>${t("executionSummaryRuns")}</span><strong>${escapeHtml(executionSummary.total_runs)}</strong></div></div>
                <div class="criterion-card"><div class="criterion-head"><span>${t("executionSummarySteps")}</span><strong>${escapeHtml(executionSummary.step_completion_rate)}%</strong></div><p class="step-meta">${escapeHtml(executionSummary.completed_steps)} / ${escapeHtml(executionSummary.total_steps)}</p></div>
                <div class="criterion-card"><div class="criterion-head"><span>${t("executionSummaryQuality")}</span><strong>${escapeHtml(executionSummary.quality_completion_rate)}%</strong></div><p class="step-meta">${escapeHtml(executionSummary.completed_quality_items)} / ${escapeHtml(executionSummary.total_quality_items)}</p></div>
              </div>
              ${
                executionSummary.latest_runs && executionSummary.latest_runs.length
                  ? `<h3>${t("executionSummaryLatest")}</h3><ul>${executionSummary.latest_runs
                      .map(
                        (run) =>
                          `<li>${escapeHtml(formatDateTime(run.created_at))}: ${escapeHtml(run.executor)} · ${escapeHtml(run.completed_steps)} / ${escapeHtml(run.total_steps)}</li>`,
                      )
                      .join("")}</ul>`
                  : ""
              }
            </section>
          `;
        };
        const workflowActions = (record) => {
          if (currentUser && !reviewerRoleValues.includes(currentUser.role)) {
            return "";
          }
          const actions = [];
          if (record.workflow_status === "ai_draft") {
            actions.push(["expert_review", t("historySendReview")], ["rejected", t("historyReject")]);
          } else if (record.workflow_status === "expert_review") {
            actions.push(["approved", t("historyApprove")], ["rejected", t("historyReject")]);
          } else if (record.workflow_status === "approved") {
            actions.push(["expert_review", t("historySendReview")]);
          } else if (record.workflow_status === "rejected") {
            actions.push(["expert_review", t("historySendReview")]);
          }
          return actions
            .map(
              ([nextStatus, label]) =>
                `<button class="secondary-action history-status" type="button" data-history-status="${escapeHtml(nextStatus)}" data-history-id="${escapeHtml(record.instruction_id)}" data-history-version="${escapeHtml(record.version)}">${label}</button>`,
            )
            .join("");
        };
        return `
          <div class="instruction">
            ${renderExecutionSummary()}
            <section>
              <h3>${t("historyTitle")}</h3>
              <div class="history-list">
              ${historyRecords
                .map(
                  (record) => `
                    <div class="history-row">
                      <div>
                      <h3 class="history-title">${escapeHtml(record.title)}</h3>
                      <p class="history-date">${t("historyVersion")}: ${escapeHtml(record.version)} · ${escapeHtml(formatDateTime(record.created_at))}</p>
                      <p class="criterion-note">${t("overallScore")}: ${escapeHtml(record.overall_score)}/100</p>
                      <div class="doc-meta">
                        ${renderBadge(record.risk_level, translations[language].riskLabels[record.risk_level] || record.risk_level)}
                        ${renderBadge(record.workflow_status, record.workflow_status_label || record.workflow_status)}
                      </div>
                      ${record.reviewer ? `<p class="step-meta">${t("historyReviewer")}: ${escapeHtml(record.reviewer)}${record.reviewer_role ? ` · ${t("workflowReviewerRole")}: ${escapeHtml(translations[language].reviewerRoles[record.reviewer_role] || record.reviewer_role)}` : ""}</p>` : ""}
	                      ${record.review_comment ? `<p class="step-meta">${t("historyComment")}: ${escapeHtml(record.review_comment)}</p>` : ""}
	                      <p class="step-meta">${t("historySources")}: ${escapeHtml(record.source_count)} · ${t("historySteps")}: ${escapeHtml(record.step_count)}</p>
	                      </div>
	                      <div class="inline-actions">
	                        <button class="secondary-action history-open" type="button" data-history-id="${escapeHtml(record.instruction_id)}" data-history-version="${escapeHtml(record.version)}">${t("historyOpen")}</button>
	                        ${workflowActions(record)}
	                      </div>
	                    </div>
                  `,
                )
                .join("")}
              </div>
            </section>
          </div>
        `;
      }

      async function loadHistory(promptForToken = false) {
        try {
          const response = await apiFetch("/api/instructions/history", {}, promptForToken);
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          const payload = await response.json();
          historyRecords = payload.records || [];
          const summaryResponse = await apiFetch("/api/instructions/history/execution-summary", {}, false);
          if (summaryResponse.ok) {
            executionSummary = await summaryResponse.json();
          } else {
            executionSummary = null;
          }
          if (activeTab === "history") {
            renderResult();
          }
        } catch (error) {
          historyRecords = [];
          executionSummary = null;
        }
      }

      async function saveCurrentInstructionVersion() {
        if (!lastPayload) {
          return;
        }
        saveHistoryButton.disabled = true;
        status.textContent = t("historyLoading");
        status.classList.remove("error");
        try {
          const response = await apiFetch("/api/instructions/history", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ payload: lastPayload }),
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          const payload = await response.json();
          currentHistoryRecord = payload.record;
          currentAuditEvents = [];
          await loadHistory();
          status.textContent = t("historySaved");
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        } finally {
          saveHistoryButton.disabled = !lastPayload;
        }
      }

      async function openHistoryVersion(instructionId, version) {
        status.textContent = t("historyLoading");
        status.classList.remove("error");
        try {
          const response = await apiFetch(`/api/instructions/history/${encodeURIComponent(instructionId)}/versions/${encodeURIComponent(version)}`);
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          const detail = await response.json();
          lastPayload = detail.payload;
          currentHistoryRecord = detail.record;
          currentAuditEvents = detail.audit_events || [];
          activeTab = "instruction";
          syncTabState();
          status.textContent = t("statusReady");
          renderResult();
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        }
      }

      function openWorkflowDecision(instructionId, version, nextStatus) {
        workflowModalOpener = document.activeElement;
        pendingWorkflowDecision = { instructionId, version, nextStatus };
        workflowReviewerInput.value = currentUser ? currentUser.full_name : "";
        workflowReviewerRoleSelect.value =
          currentUser && reviewerRoleValues.includes(currentUser.role)
            ? currentUser.role
            : nextStatus === "approved"
              ? "safety"
              : "master";
        workflowReviewerInput.disabled = Boolean(currentUser);
        workflowReviewerRoleSelect.disabled = Boolean(currentUser);
        workflowCommentInput.value = "";
        workflowResolvedBlockersInput.value = "";
        workflowModal.hidden = false;
        (currentUser ? workflowCommentInput : workflowReviewerInput).focus();
      }

      function closeWorkflowDecision() {
        pendingWorkflowDecision = null;
        workflowModal.hidden = true;
        if (workflowModalOpener && typeof workflowModalOpener.focus === "function") {
          workflowModalOpener.focus();
        }
        workflowModalOpener = null;
      }

      async function updateHistoryStatus(decision) {
        const resolvedBlockers = workflowResolvedBlockersInput.value
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean);
        status.textContent = t("historyLoading");
        status.classList.remove("error");
        try {
          const response = await apiFetch(`/api/instructions/history/${encodeURIComponent(decision.instructionId)}/versions/${encodeURIComponent(decision.version)}/workflow`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              status: decision.nextStatus,
              reviewer: workflowReviewerInput.value.trim(),
              reviewer_role: workflowReviewerRoleSelect.value,
              comment: workflowCommentInput.value.trim(),
              resolved_blockers: resolvedBlockers,
            }),
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          closeWorkflowDecision();
          await loadHistory();
          status.textContent = t("historyUpdated");
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        }
      }

      function readExecutionPayload() {
        const executor = (document.getElementById("execution_executor") || {}).value || "";
        const notes = (document.getElementById("execution_notes") || {}).value || "";
        const collectItems = (kind) =>
          Array.from(document.querySelectorAll(`[data-execution-kind="${kind}"]`)).map((input) => ({
            label: input.dataset.executionLabel || "",
            completed: input.checked,
          }));
        return {
          executor: executor.trim(),
          notes: notes.trim(),
          steps: collectItems("step"),
          quality_items: collectItems("quality"),
        };
      }

      async function saveExecutionRun() {
        if (!currentHistoryRecord) {
          status.textContent = t("executionSaveUnavailable");
          status.classList.add("error");
          return;
        }
        const payload = readExecutionPayload();
        if (!payload.executor || payload.executor.length < 2) {
          status.textContent = `${t("statusError")}: ${t("executionExecutor")}`;
          status.classList.add("error");
          return;
        }
        status.textContent = t("historyLoading");
        status.classList.remove("error");
        try {
          const response = await apiFetch(
            `/api/instructions/history/${encodeURIComponent(currentHistoryRecord.instruction_id)}/versions/${encodeURIComponent(currentHistoryRecord.version)}/execution`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            },
          );
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          status.textContent = t("executionSaved");
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        }
      }

      function formSubmitButton(formElement) {
        return (
          Array.from(formElement.elements).find(
            (element) => element.type === "submit" && element.tagName === "BUTTON",
          ) || null
        );
      }

      async function submitForm(event) {
        event.preventDefault();
        currentHistoryRecord = null;
        currentAuditEvents = [];
        status.textContent = t("statusLoading");
        status.classList.remove("error");
        formSubmitButton(form).disabled = true;

        try {
          const endpoint = document.getElementById("use_context").checked
            ? "/api/instructions/generate-with-context"
            : "/api/instructions/generate";
          const response = await apiFetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(readFormPayload()),
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          lastPayload = await response.json();
          currentHistoryRecord = null;
          currentAuditEvents = [];
          activeTab = "instruction";
          syncTabState();
          status.textContent = t("statusReady");
          renderResult();
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        } finally {
          formSubmitButton(form).disabled = false;
        }
      }

      async function submitVideo() {
        const fileInput = document.getElementById("video_file");
        const file = fileInput.files && fileInput.files[0];
        const videoUrl = document.getElementById("video_url").value.trim();
        if (!file && !videoUrl) {
          status.textContent = t("videoStatusNoInput");
          status.classList.add("error");
          return;
        }
        if (file && videoUrl) {
          status.textContent = t("videoStatusBothInputs");
          status.classList.add("error");
          return;
        }
        status.textContent = t("videoStatusLoading");
        status.classList.remove("error");
        lastVideoPayload = null;
        setVideoJobBusy(true);
        if (activeTab === "video") {
          renderResult();
        }
        try {
          const formData = new FormData();
          if (file) {
            formData.append("file", file);
          } else {
            formData.append("video_url", videoUrl);
            formData.append("visual_quality", document.getElementById("visual_quality").value);
          }
          formData.append("max_keyframes", document.getElementById("max_keyframes").value);
          const idempotencyKey = window.crypto && typeof window.crypto.randomUUID === "function"
            ? window.crypto.randomUUID()
            : `video-${Date.now()}-${Math.random().toString(16).slice(2)}`;
          const response = await apiFetch("/api/videos/jobs", {
            method: "POST",
            headers: { "Idempotency-Key": idempotencyKey },
            body: formData,
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          const job = await response.json();
          currentVideoJobId = job.job_id;
          sessionStorage.setItem("currentVideoJobId", currentVideoJobId);
          await pollVideoJob(currentVideoJobId, job);
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
          if (!currentVideoJobId) setVideoJobBusy(false);
        }
      }

      function setVideoJobBusy(isBusy) {
        ["video_url", "video_file", "max_keyframes", "visual_quality"].forEach((id) => {
          document.getElementById(id).disabled = isBusy;
        });
        videoButton.disabled = isBusy;
        videoGenerateButton.disabled =
          isBusy || !(lastVideoPayload && lastVideoPayload.keyframes && lastVideoPayload.keyframes.length);
        videoJobProgress.hidden = !isBusy;
        videoCancelButton.disabled = !isBusy;
      }

      function renderVideoJobProgress(job) {
        const progress = Math.max(0, Math.min(100, Number(job.progress_percent) || 0));
        // The bar is a styled div, not <progress>: width comes from a custom
        // property. setProperty is CSSOM, so the CSP ban on style attributes holds.
        videoJobProgressBar.style.setProperty("--progress-value", `${progress}%`);
        videoJobProgressBar.setAttribute("aria-valuenow", String(progress));
        videoJobProgressBar.textContent = `${progress}%`;
        videoJobProgressLabel.textContent = job.cancel_requested
          ? t("videoStatusCancelRequested")
          : t("videoStatusProgress").replace("{progress}", progress);
        status.textContent = videoJobProgressLabel.textContent;
        status.classList.remove("error");
      }

      async function pollVideoJob(jobId, initialJob = null) {
        setVideoJobBusy(true);
        let job = initialJob;
        while (currentVideoJobId === jobId) {
          if (!job) {
            const response = await apiFetch(`/api/videos/jobs/${encodeURIComponent(jobId)}`);
            if (!response.ok) throw new Error(await responseErrorMessage(response));
            job = await response.json();
          }
          renderVideoJobProgress(job);
          if (job.status === "succeeded") {
            const response = await apiFetch(`/api/videos/jobs/${encodeURIComponent(jobId)}/result`);
            if (!response.ok) throw new Error(await responseErrorMessage(response));
            lastVideoPayload = await response.json();
            finishVideoJob();
            videoGenerateButton.disabled = !(lastVideoPayload.keyframes && lastVideoPayload.keyframes.length);
            activeTab = "video";
            syncTabState();
            status.textContent = videoGenerateButton.disabled ? t("videoStatusNoKeyframes") : t("videoStatusReady");
            status.classList.toggle("error", videoGenerateButton.disabled);
            renderResult();
            return;
          }
          if (job.status === "failed") {
            const message = job.error_message || t("videoStatusFailed");
            finishVideoJob();
            status.textContent = `${t("videoStatusFailed")}: ${message}`;
            status.classList.add("error");
            return;
          }
          if (job.status === "cancelled") {
            finishVideoJob();
            status.textContent = t("videoStatusCancelled");
            status.classList.remove("error");
            return;
          }
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          job = null;
        }
      }

      function finishVideoJob() {
        currentVideoJobId = "";
        sessionStorage.removeItem("currentVideoJobId");
        setVideoJobBusy(false);
      }

      async function cancelVideoJob() {
        if (!currentVideoJobId) return;
        videoCancelButton.disabled = true;
        status.textContent = t("videoStatusCancelRequested");
        try {
          const response = await apiFetch(`/api/videos/jobs/${encodeURIComponent(currentVideoJobId)}`, {
            method: "DELETE",
          });
          if (!response.ok) throw new Error(await responseErrorMessage(response));
          renderVideoJobProgress(await response.json());
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
          videoCancelButton.disabled = false;
        }
      }

      async function resumeVideoJob() {
        if (!currentVideoJobId) return;
        try {
          await pollVideoJob(currentVideoJobId);
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
          setVideoJobBusy(true);
          videoCancelButton.disabled = false;
        }
      }

      async function submitVideoInstruction() {
        if (!lastVideoPayload) {
          status.textContent = t("videoStatusNoProcessedVideo");
          status.classList.add("error");
          return;
        }
        if (!lastVideoPayload.keyframes || !lastVideoPayload.keyframes.length) {
          status.textContent = t("videoStatusNoKeyframes");
          status.classList.add("error");
          return;
        }
        const payload = buildVideoInstructionPayload(lastVideoPayload);
        applyVideoPayloadToForm(payload);
        status.textContent = t("videoInstructionLoading");
        status.classList.remove("error");
        videoGenerateButton.disabled = true;
        formSubmitButton(form).disabled = true;
        try {
          const response = await apiFetch("/api/instructions/generate-from-video", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...payload,
              keyframes: lastVideoPayload.keyframes || [],
              frame_analyses: lastVideoPayload.frame_analyses || [],
              video_segments: lastVideoPayload.video_segments || [],
            }),
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          lastPayload = await response.json();
          currentHistoryRecord = null;
          currentAuditEvents = [];
          activeTab = "instruction";
          syncTabState();
          status.textContent = t("statusReady");
          renderResult();
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        } finally {
          videoGenerateButton.disabled = !(lastVideoPayload && lastVideoPayload.keyframes && lastVideoPayload.keyframes.length);
          formSubmitButton(form).disabled = false;
        }
      }

      function readEditedPayload() {
        const payload = structuredClone(lastPayload);
        const instruction = payload.instruction;
        result.querySelectorAll("[data-editor-field]").forEach((field) => {
          const key = field.dataset.editorField;
          const value = field.value.trim();
          instruction[key] = value || null;
        });
        ["title", "purpose", "scope", "operator_level"].forEach((key) => {
          if (!instruction[key]) {
            instruction[key] = t("noData");
          }
        });
        editorListFields.forEach((key) => {
          const field = result.querySelector(`[data-editor-list="${key}"]`);
          if (field) {
            instruction[key] = textToList(field.value, requiredEditorListFields.has(key));
          }
        });
        instruction.steps = Array.from(result.querySelectorAll("[data-editor-step]")).map((container, index) => {
          const valueFor = (name) => {
            const field = container.querySelector(`[data-step-field="${name}"]`);
            return field ? field.value.trim() : "";
          };
          return {
            number: index + 1,
            action: valueFor("action") || t("noData"),
            expected_result: valueFor("expected_result") || t("noData"),
            safety_note: valueFor("safety_note") || null,
            verification_method: valueFor("verification_method") || null,
            common_mistakes: textToList(valueFor("common_mistakes")),
          };
        });
        payload.markdown = "";
        return payload;
      }

      async function rebuildEditedInstruction() {
        if (!lastPayload) {
          return;
        }
        status.textContent = t("statusLoading");
        status.classList.remove("error");
        try {
          const response = await apiFetch("/api/instructions/rebuild", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ payload: readEditedPayload(), source_request: optionalSourceRequestPayload() }),
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          lastPayload = await response.json();
          currentHistoryRecord = null;
          currentAuditEvents = [];
          status.textContent = t("editorSaved");
          renderResult();
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        }
      }

      async function improveCurrentInstruction() {
        if (!lastPayload) {
          return;
        }
        const sourcePayload = activeTab === "editor" ? readEditedPayload() : lastPayload;
        status.textContent = t("statusLoading");
        status.classList.remove("error");
        improveInstructionButton.disabled = true;
        try {
          const response = await apiFetch("/api/instructions/improve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ payload: sourcePayload, source_request: optionalSourceRequestPayload() }),
          });
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response));
          }
          lastPayload = await response.json();
          currentHistoryRecord = null;
          currentAuditEvents = [];
          status.textContent = t("editorImproved");
          if (activeTab !== "editor") {
            activeTab = "instruction";
            syncTabState();
          }
          renderResult();
        } catch (error) {
          status.textContent = `${t("statusError")}: ${error.message}`;
          status.classList.add("error");
        } finally {
          improveInstructionButton.disabled = !lastPayload;
        }
      }

      async function responseErrorMessage(response) {
        try {
          const payload = await response.json();
          if (payload.error && payload.error.message) {
            return String(payload.error.message);
          }
          if (payload.detail) {
            if (Array.isArray(payload.detail)) {
              return payload.detail
                .map((item) => {
                  if (typeof item === "string") {
                    return item;
                  }
                  const location = Array.isArray(item.loc) ? item.loc.join(".") : "";
                  const message = item.msg || JSON.stringify(item);
                  return location ? `${location}: ${message}` : message;
                })
                .join("; ");
            }
            return String(payload.detail);
          }
        } catch (_) {
          // Keep the fallback below when the response body is not JSON.
        }
        return `HTTP ${response.status}`;
      }

      document.querySelectorAll("[data-lang]").forEach((button) => {
        button.addEventListener("click", () => {
          language = button.dataset.lang;
          localStorage.setItem("language", language);
          localizeStaticText();
        });
      });

      authOpenButton.addEventListener("click", openAuthModal);
      authLogoutButton.addEventListener("click", logoutAuth);
      authModeSelect.addEventListener("change", syncAuthControls);
      authForm.addEventListener("submit", submitAuth);
      authCancelButton.addEventListener("click", closeAuthModal);
      authModal.addEventListener("click", (event) => {
        if (event.target === authModal) {
          closeAuthModal();
        }
      });
      authModal.addEventListener("keydown", (event) => handleModalKeydown(event, authModal, closeAuthModal));

      tabButtons.forEach((button) => {
        button.addEventListener("click", () => {
          activeTab = button.dataset.resultView;
          syncTabState();
          if (activeTab === "history") {
            loadHistory(true);
          }
          renderResult();
        });
        button.addEventListener("keydown", (event) => {
          const currentIndex = tabButtons.indexOf(button);
          let nextIndex = null;
          if (event.key === "ArrowRight" || event.key === "ArrowDown") {
            nextIndex = (currentIndex + 1) % tabButtons.length;
          }
          if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
            nextIndex = (currentIndex - 1 + tabButtons.length) % tabButtons.length;
          }
          if (event.key === "Home") nextIndex = 0;
          if (event.key === "End") nextIndex = tabButtons.length - 1;
          if (nextIndex === null) return;
          event.preventDefault();
          tabButtons[nextIndex].click();
          tabButtons[nextIndex].focus();
        });
      });

      const sidebar = document.querySelector(".sidebar");
      const sidebarLinks = Array.from(document.querySelectorAll("[data-sidebar-target]"));
      const sidebarCollapse = document.getElementById("sidebar-collapse");
      const mobileMenuToggle = document.getElementById("mobile-menu-toggle");
      const mobileMenuClose = document.getElementById("mobile-menu-close");
      const sidebarBackdrop = document.getElementById("sidebar-backdrop");

      function isMobileNavigation() {
        return window.matchMedia("(max-width: 820px)").matches;
      }

      function closeMobileMenu({ restoreFocus = false } = {}) {
        sidebar.classList.remove("is-mobile-open");
        sidebarBackdrop.hidden = true;
        sidebarBackdrop.classList.remove("is-active");
        document.querySelector(".app-frame").classList.remove("mobile-menu-open");
        document.body.classList.remove("mobile-menu-open");
        mobileMenuToggle.setAttribute("aria-expanded", "false");
        if (restoreFocus) mobileMenuToggle.focus();
      }

      function openMobileMenu() {
        if (!isMobileNavigation()) return;
        sidebar.classList.add("is-mobile-open");
        sidebarBackdrop.hidden = false;
        sidebarBackdrop.classList.add("is-active");
        document.querySelector(".app-frame").classList.add("mobile-menu-open");
        document.body.classList.add("mobile-menu-open");
        mobileMenuToggle.setAttribute("aria-expanded", "true");
        sidebarLinks.find((link) => link.getAttribute("aria-current") === "page")?.focus();
      }

      function syncSidebarState(target) {
        sidebarLinks.forEach((link) => {
          const active = link.dataset.sidebarTarget === target;
          link.classList.toggle("is-active", active);
          if (active) link.setAttribute("aria-current", "page");
          else link.removeAttribute("aria-current");
        });
      }

      sidebarLinks.forEach((link) => {
        link.addEventListener("click", () => {
          const target = link.dataset.sidebarTarget;
          closeMobileMenu();
          if (target === "generator") {
            document.getElementById("instruction-form").scrollIntoView({ behavior: "smooth", block: "start" });
            syncSidebarState("generator");
            return;
          }
          document.querySelector(".result-panel").scrollIntoView({ behavior: "smooth", block: "start" });
        });
      });

      mobileMenuToggle.addEventListener("click", openMobileMenu);
      mobileMenuClose.addEventListener("click", () => closeMobileMenu({ restoreFocus: true }));
      sidebarBackdrop.addEventListener("click", () => closeMobileMenu({ restoreFocus: true }));
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && sidebar.classList.contains("is-mobile-open")) {
          closeMobileMenu({ restoreFocus: true });
        }
      });
      window.addEventListener("resize", () => {
        if (!isMobileNavigation()) closeMobileMenu();
      });

      sidebarCollapse.addEventListener("click", () => {
        const collapsed = sidebar.classList.toggle("is-collapsed");
        document.querySelector(".app-frame").classList.toggle("sidebar-is-collapsed", collapsed);
        sidebarCollapse.setAttribute("aria-expanded", String(!collapsed));
      });

      form.addEventListener("submit", submitForm);
      sampleButton.addEventListener("click", () => {
        const sample = sampleCases.find((item) => item.id === document.getElementById("sample_case").value);
        if (sample) {
          applyInstructionPayloadToForm(sample.payload);
          status.textContent = t("statusIdle");
          status.classList.remove("error");
        }
      });
      document.getElementById("use_context").addEventListener("change", syncContextControls);
      document.getElementById("video_file").addEventListener("change", () =>
        syncFilePicker("video_file", "video-file-name"),
      );
      document.getElementById("document_file").addEventListener("change", () =>
        syncFilePicker("document_file", "document-file-name"),
      );
      ["video_url", "video_file", "max_keyframes", "visual_quality"].forEach((id) => {
        document.getElementById(id).addEventListener("change", resetProcessedVideoState);
      });
      document.getElementById("video_url").addEventListener("input", resetProcessedVideoState);
      [
        ["video-tools-toggle", "video-tools"],
        ["document-tools-toggle", "document-tools"],
      ].forEach(([toggleId, bodyId]) => {
        const toggle = document.getElementById(toggleId);
        if (!toggle) return;
        toggle.addEventListener("click", () => {
          const expanded = toggle.getAttribute("aria-expanded") === "true";
          toggle.setAttribute("aria-expanded", String(!expanded));
          document.getElementById(bodyId).hidden = expanded;
        });
        document.getElementById(bodyId).hidden = toggle.getAttribute("aria-expanded") !== "true";
      });
      videoButton.addEventListener("click", submitVideo);
      videoCancelButton.addEventListener("click", cancelVideoJob);
      videoGenerateButton.addEventListener("click", submitVideoInstruction);
      documentButton.addEventListener("click", uploadDocument);
      improveInstructionButton.addEventListener("click", improveCurrentInstruction);
      saveHistoryButton.addEventListener("click", saveCurrentInstructionVersion);
      workflowForm.addEventListener("submit", (event) => {
        event.preventDefault();
        if (pendingWorkflowDecision) {
          updateHistoryStatus(pendingWorkflowDecision);
        }
      });
      workflowCancelButton.addEventListener("click", closeWorkflowDecision);
      workflowModal.addEventListener("click", (event) => {
        if (event.target === workflowModal) {
          closeWorkflowDecision();
        }
      });
      workflowModal.addEventListener("keydown", (event) =>
        handleModalKeydown(event, workflowModal, closeWorkflowDecision),
      );
      result.addEventListener("click", (event) => {
        const editorAction = event.target.closest("[data-editor-action]");
        if (editorAction && editorAction.dataset.editorAction === "apply") {
          rebuildEditedInstruction();
          return;
        }
        if (editorAction && editorAction.dataset.editorAction === "improve") {
          improveCurrentInstruction();
          return;
        }
        const executionAction = event.target.closest("[data-execution-action]");
        if (executionAction && executionAction.dataset.executionAction === "toggle-shop-floor") {
          shopFloorMode = Boolean(executionAction.checked);
          localStorage.setItem("shopFloorMode", String(shopFloorMode));
          renderResult();
          return;
        }
        if (executionAction && executionAction.dataset.executionAction === "save") {
          saveExecutionRun();
          return;
        }
        const openButton = event.target.closest(".history-open");
        if (openButton) {
          openHistoryVersion(openButton.dataset.historyId, openButton.dataset.historyVersion);
          return;
        }
        const statusButton = event.target.closest(".history-status");
        if (statusButton) {
          openWorkflowDecision(
            statusButton.dataset.historyId,
            statusButton.dataset.historyVersion,
            statusButton.dataset.historyStatus,
          );
        }
      });
      exportMarkdownButton.addEventListener("click", () => {
        if (lastPayload) {
          downloadTextFile(resultFilename("md"), lastPayload.markdown || "", "text/markdown;charset=utf-8");
        }
      });
      exportPdfButton.addEventListener("click", downloadPdfFile);
      exportJsonButton.addEventListener("click", () => {
        if (lastPayload) {
          downloadTextFile(resultFilename("json"), JSON.stringify(lastPayload, null, 2), "application/json;charset=utf-8");
        }
      });
      videoGenerateButton.disabled = true;
      syncTabState();
      syncSidebarState("generator");
      syncExportButtons();
      loadHistory();
      loadAuthCapabilities();
      loadCurrentUser().then(resumeVideoJob);
      localizeStaticText();
