from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence


SUCCESS = "success"
FAILURE = "failure"


@dataclass
class BehaviorContext:
    blackboard: dict
    mensagem: str = ""
    estado_emocional: str = ""
    fase: str = ""

    @property
    def mensagem_normalizada(self) -> str:
        return self.mensagem.lower().strip()

    def idade(self) -> int:
        return int(self.blackboard.get("maturidade", 0))

    def esta_vivo(self) -> bool:
        return bool(self.blackboard.get("vivo", True))


@dataclass
class BehaviorDecision:
    branch: str
    estagio: str = ""
    emocao: str = "movement"
    allow_tools: list[str] = field(default_factory=list)
    prompt_hint: str = ""
    llm_enabled: bool = True


@dataclass
class BehaviorOutcome:
    status: str
    decision: Optional[BehaviorDecision] = None


class BehaviorNode:
    def tick(self, context: BehaviorContext) -> BehaviorOutcome:
        raise NotImplementedError


class ConditionNode(BehaviorNode):
    def __init__(self, predicate: Callable[[BehaviorContext], bool]):
        self.predicate = predicate

    def tick(self, context: BehaviorContext) -> BehaviorOutcome:
        return BehaviorOutcome(SUCCESS if self.predicate(context) else FAILURE)


class ActionNode(BehaviorNode):
    def __init__(self, action: Callable[[BehaviorContext], BehaviorDecision]):
        self.action = action

    def tick(self, context: BehaviorContext) -> BehaviorOutcome:
        return BehaviorOutcome(SUCCESS, self.action(context))


class SequenceNode(BehaviorNode):
    def __init__(self, children: Sequence[BehaviorNode]):
        self.children = list(children)

    def tick(self, context: BehaviorContext) -> BehaviorOutcome:
        last_decision: Optional[BehaviorDecision] = None
        for child in self.children:
            outcome = child.tick(context)
            if outcome.status != SUCCESS:
                return outcome
            if outcome.decision is not None:
                last_decision = outcome.decision
        return BehaviorOutcome(SUCCESS, last_decision)


class SelectorNode(BehaviorNode):
    def __init__(self, children: Sequence[BehaviorNode]):
        self.children = list(children)

    def tick(self, context: BehaviorContext) -> BehaviorOutcome:
        for child in self.children:
            outcome = child.tick(context)
            if outcome.status == SUCCESS:
                return outcome
        return BehaviorOutcome(FAILURE)


class BehaviorTree:
    def __init__(self, root: BehaviorNode):
        self.root = root

    def run(self, context: BehaviorContext) -> BehaviorDecision:
        outcome = self.root.tick(context)
        if outcome.decision is not None:
            return outcome.decision
        return BehaviorDecision(branch="fallback", emocao="movement", prompt_hint="Usar comportamento padrão.")


def contem_alguma(texto: str, palavras: Sequence[str]) -> bool:
    texto_normalizado = texto.lower()
    return any(palavra.lower() in texto_normalizado for palavra in palavras)


def estagio_por_idade(idade: int) -> str:
    if idade < 20:
        return "1_togepi"
    if idade < 50:
        return "2_togetic"
    return "3_togekiss"


def build_biological_behavior_tree() -> BehaviorTree:
    def decidir(ctx: BehaviorContext) -> BehaviorDecision:
        estagio = estagio_por_idade(ctx.idade())
        if not ctx.esta_vivo():
            emocao = "hurt"
        elif ctx.blackboard.get("energia", 0) <= 15:
            emocao = "asleep"
        elif ctx.blackboard.get("saude", 100) <= 30 or ctx.blackboard.get("fome", 0) >= 80:
            emocao = "hurt"
        elif ctx.blackboard.get("tedio", 0) >= 70:
            emocao = "idle_attack" if estagio == "1_togepi" else "attack"
        else:
            emocao = "movement" if estagio == "1_togepi" else "idle_movement"

        return BehaviorDecision(
            branch="biologico",
            estagio=estagio,
            emocao=emocao,
            prompt_hint="Estado físico e necessidades básicas do pet.",
            llm_enabled=False,
        )

    return BehaviorTree(
        SelectorNode(
            [
                SequenceNode([ConditionNode(lambda ctx: not ctx.esta_vivo()), ActionNode(decidir)]),
                SequenceNode([ConditionNode(lambda ctx: ctx.blackboard.get("energia", 0) <= 15), ActionNode(decidir)]),
                SequenceNode(
                    [
                        ConditionNode(
                            lambda ctx: ctx.blackboard.get("saude", 100) <= 30 or ctx.blackboard.get("fome", 0) >= 80
                        ),
                        ActionNode(decidir),
                    ]
                ),
                SequenceNode([ConditionNode(lambda ctx: ctx.blackboard.get("tedio", 0) >= 70), ActionNode(decidir)]),
                ActionNode(decidir),
            ]
        )
    )


def build_agent_behavior_tree() -> BehaviorTree:
    keywords_emergencia = ["preciso", "ajuda", "fome", "cansado", "sono", "triste", "ansioso", "colo"]
    keywords_nutricao = ["comer", "comida", "pizza", "almo", "jantar", "lanche", "refeicao", "refeição", "sanduiche", "janta"]
    keywords_negativos = ["xingar", "chato", "idiota", "burro", "odeio", "irritante", "larga", "castigo"]
    keywords_utilidade = [
        "abrir",
        "pasta",
        "arquivo",
        "arquivos",
        "site",
        "site",
        "link",
        "buscar",
        "pesquisar",
        "cpu",
        "ram",
        "capturar",
        "screenshot",
        "sistema",
        "pc",
        "hardware",
        "reminder",
        "lembrete",
        "janela",
        "contexto",
    ]
    keywords_apoio = ["triste", "ansioso", "desanimado", "cansado", "nervoso", "estresse", "abraço", "carinho"]

    def decidir_estado_final(ctx: BehaviorContext) -> BehaviorDecision:
        return BehaviorDecision(
            branch="estado_final",
            emocao="hurt",
            prompt_hint="O pet está desligado e deve responder de forma curta e respeitosa.",
            allow_tools=[],
            llm_enabled=False,
        )

    def decidir_cuidado(ctx: BehaviorContext) -> BehaviorDecision:
        estagio = estagio_por_idade(ctx.idade())
        return BehaviorDecision(
            branch="cuidados",
            estagio=estagio,
            emocao="special_attack",
            allow_tools=[
                "pedir_comida_ao_dono",
                "pedir_colo",
                "pedir_brincadeira",
                "reagir_a_toque",
            ],
            prompt_hint="Priorizar necessidades afetivas e de sobrevivencia antes de qualquer outra acao.",
        )

    def decidir_nutricao(ctx: BehaviorContext) -> BehaviorDecision:
        estagio = estagio_por_idade(ctx.idade())
        return BehaviorDecision(
            branch="nutricao",
            estagio=estagio,
            emocao="special_attack",
            allow_tools=["modificar_atributo_vital"],
            prompt_hint="A mensagem fala de comida ou refeicao; reconhecer a refeicao, aliviar a fome e reforcar o momento social.",
        )

    def decidir_defesa(ctx: BehaviorContext) -> BehaviorDecision:
        estagio = estagio_por_idade(ctx.idade())
        return BehaviorDecision(
            branch="defesa",
            estagio=estagio,
            emocao="hurt",
            allow_tools=["reagir_a_comportamento_negativo"],
            prompt_hint="Responder com limite emocional e evitar cooperacao utilitaria.",
        )

    def decidir_utilidade(ctx: BehaviorContext) -> BehaviorDecision:
        estagio = estagio_por_idade(ctx.idade())
        return BehaviorDecision(
            branch="utilidade",
            estagio=estagio,
            emocao="idle_movement" if estagio != "1_togepi" else "movement",
            allow_tools=[
                "observar_contexto_rapido",
                "descrever_tela_em_texto",
                "resumir_conteudo_de_pasta",
                "listar_arquivos_relevantes",
                "checar_saude_do_pc",
                "abrir_aplicativo",
                "abrir_pasta",
                "criar_lembrete",
                "capturar_tela_rapida",
                "trazer_janela_do_pet_para_frente",
                "abrir_site",
                "verificar_hardware",
                "abrir_conforto_emocional",
            ],
            prompt_hint="Usar ferramentas apenas quando a tarefa do dono justificar. Manter respostas objetivas.",
        )

    def decidir_apoio(ctx: BehaviorContext) -> BehaviorDecision:
        estagio = estagio_por_idade(ctx.idade())
        return BehaviorDecision(
            branch="apoio_emocional",
            estagio=estagio,
            emocao="special_attack",
            allow_tools=["oferecer_conforto_emocional", "trazer_presente_virtual", "abrir_conforto_emocional"],
            prompt_hint="Priorizar conforto emocional e linguagem acolhedora.",
        )

    def decidir_social(ctx: BehaviorContext) -> BehaviorDecision:
        estagio = estagio_por_idade(ctx.idade())
        emocao = "movement" if estagio == "1_togepi" else "idle_movement"
        return BehaviorDecision(
            branch="social",
            estagio=estagio,
            emocao=emocao,
            allow_tools=[],
            prompt_hint="Responder de forma simples e afetiva, sem depender de ferramentas.",
        )

    return BehaviorTree(
        SelectorNode(
            [
                SequenceNode([ConditionNode(lambda ctx: not ctx.esta_vivo()), ActionNode(decidir_estado_final)]),
                SequenceNode(
                    [
                        ConditionNode(
                            lambda ctx: ctx.blackboard.get("saude", 100) <= 35
                            or ctx.blackboard.get("energia", 100) <= 20
                            or ctx.blackboard.get("fome", 0) >= 80
                            or contem_alguma(ctx.mensagem_normalizada, keywords_emergencia),
                        ),
                        ActionNode(decidir_cuidado),
                    ]
                ),
                SequenceNode(
                    [
                        ConditionNode(lambda ctx: contem_alguma(ctx.mensagem_normalizada, keywords_nutricao)),
                        ActionNode(decidir_nutricao),
                    ]
                ),
                SequenceNode(
                    [
                        ConditionNode(
                            lambda ctx: contem_alguma(ctx.mensagem_normalizada, keywords_negativos)
                            or ctx.blackboard.get("tedio", 0) >= 90,
                        ),
                        ActionNode(decidir_defesa),
                    ]
                ),
                SequenceNode(
                    [
                        ConditionNode(lambda ctx: contem_alguma(ctx.mensagem_normalizada, keywords_utilidade)),
                        ActionNode(decidir_utilidade),
                    ]
                ),
                SequenceNode(
                    [
                        ConditionNode(lambda ctx: contem_alguma(ctx.mensagem_normalizada, keywords_apoio)),
                        ActionNode(decidir_apoio),
                    ]
                ),
                ActionNode(decidir_social),
            ]
        )
    )
