export const testsData = [
  {
    id: 'SDS',
    icon: 'assessment',
    title: '抑郁自评量表 (SDS)',
    desc: '20道题，测试你近期的情绪状态，评估抑郁倾向。',
    type: 'score',
    questions: [
      { title: '1. 我觉得平常心境低落，或甚至有点忧愁。', reverse: false },
      { title: '2. 我觉得早晨的心情最好。', reverse: true },
      { title: '3. 我会有一阵阵哭泣或觉得想哭。', reverse: false },
      { title: '4. 我晚上睡眠不好。', reverse: false },
      { title: '5. 我吃得跟平常一样多。', reverse: true },
      { title: '6. 我与异性接触时和以往一样感到愉快。', reverse: true },
      { title: '7. 我发觉我的体重在下降。', reverse: false },
      { title: '8. 我有便秘的苦恼。', reverse: false },
      { title: '9. 我心跳比平时快。', reverse: false },
      { title: '10. 我无缘无故地感到疲乏。', reverse: false },
      { title: '11. 我的头脑跟平常一样清楚。', reverse: true },
      { title: '12. 我觉得经常做的事情并没有困难。', reverse: true },
      { title: '13. 我觉得不安而平静不下来。', reverse: false },
      { title: '14. 我对将来抱有希望。', reverse: true },
      { title: '15. 我比平常容易生气激动。', reverse: false },
      { title: '16. 我觉得作出决定是容易的。', reverse: true },
      { title: '17. 我觉得自己是个有用的人，有人需要我。', reverse: true },
      { title: '18. 我的生活过得很有意思。', reverse: true },
      { title: '19. 我认为如果我死了，别人会生活得好些。', reverse: false },
      { title: '20. 平常我喜欢的事情现在我也喜欢。', reverse: true },
    ],
    options: [
      { label: '没有或很少时间', val: 1 },
      { label: '小部分时间', val: 2 },
      { label: '相当多时间', val: 3 },
      { label: '绝大部分或全部时间', val: 4 },
    ],
  },
  {
    id: 'SAS',
    icon: 'assessment',
    title: '焦虑自评量表 (SAS)',
    desc: '20道题，评估你的焦虑情绪及严重程度。',
    type: 'score',
    questions: [
      { title: '1. 我觉得比平常容易紧张或着急。', reverse: false },
      { title: '2. 我无缘无故在感到害怕。', reverse: false },
      { title: '3. 我容易心里烦乱或觉得惊恐。', reverse: false },
      { title: '4. 我觉得自己可能将要发疯。', reverse: false },
      { title: '5. 我觉得一切都很好。', reverse: true },
      { title: '6. 我手脚发抖打颤。', reverse: false },
      { title: '7. 我因为头痛、颈痛和背痛而苦恼。', reverse: false },
      { title: '8. 我感觉容易衰弱和疲乏。', reverse: false },
      { title: '9. 我觉得心平气和，并且容易安静坐着。', reverse: true },
      { title: '10. 我觉得心跳得很快。', reverse: false },
      { title: '11. 我因为一阵阵头晕而苦恼。', reverse: false },
      { title: '12. 我有晕倒发作，或觉得要晕倒似的。', reverse: false },
      { title: '13. 我呼气吸气都感到很容易。', reverse: true },
      { title: '14. 我的手脚麻木和刺痛。', reverse: false },
      { title: '15. 我因为胃痛和消化不良而苦恼。', reverse: false },
      { title: '16. 我经常要小便。', reverse: false },
      { title: '17. 我的手脚常常是干燥温暖的。', reverse: true },
      { title: '18. 我脸红发热。', reverse: false },
      { title: '19. 我容易入睡并且一夜睡得很好。', reverse: true },
      { title: '20. 我做恶梦。', reverse: false },
    ],
    options: [
      { label: '没有或很少时间', val: 1 },
      { label: '小部分时间', val: 2 },
      { label: '相当多时间', val: 3 },
      { label: '绝大部分或全部时间', val: 4 },
    ],
  },
  {
    id: 'MBTI',
    icon: 'assessment',
    title: 'MBTI 精简版',
    desc: '28道题，快速测出你的16型人格类型及职业建议。',
    type: 'mbti',
    questions: [
      // E/I
      {
        title: '在聚会中，你通常：',
        options: [
          { label: '与许多人交流，包括陌生人', val: 'E' },
          { label: '只与认识的几个人交流', val: 'I' },
        ],
      },
      {
        title: '你更喜欢：',
        options: [
          { label: '很多人在周围的热闹环境', val: 'E' },
          { label: '安静的、少数人的环境', val: 'I' },
        ],
      },
      {
        title: '周末你更倾向于：',
        options: [
          { label: '出门参加活动', val: 'E' },
          { label: '宅在家里休息', val: 'I' },
        ],
      },
      {
        title: '在团队中，你更喜欢：',
        options: [
          { label: '公开表达自己的想法', val: 'E' },
          { label: '在心里默默思考', val: 'I' },
        ],
      },
      {
        title: '结识新朋友对你来说：',
        options: [
          { label: '很容易，令人兴奋', val: 'E' },
          { label: '有些困难，消耗精力', val: 'I' },
        ],
      },
      {
        title: '当你感到疲惫时，你会：',
        options: [
          { label: '找朋友聊天放松', val: 'E' },
          { label: '一个人独处恢复', val: 'I' },
        ],
      },
      {
        title: '你通常被认为是：',
        options: [
          { label: '健谈、外向的人', val: 'E' },
          { label: '安静、内敛的人', val: 'I' },
        ],
      },

      // S/N
      {
        title: '你更关注：',
        options: [
          { label: '当下的实际情况', val: 'S' },
          { label: '未来的可能性', val: 'N' },
        ],
      },
      {
        title: '你更喜欢哪种工作方式？',
        options: [
          { label: '按部就班、遵循流程', val: 'S' },
          { label: '寻找新的、创造性的方法', val: 'N' },
        ],
      },
      {
        title: '你更相信：',
        options: [
          { label: '具体的经验和事实', val: 'S' },
          { label: '直觉和预感', val: 'N' },
        ],
      },
      {
        title: '在学习新事物时，你更喜欢：',
        options: [
          { label: '看到具体的实际应用', val: 'S' },
          { label: '理解背后的概念和理论', val: 'N' },
        ],
      },
      {
        title: '你通常被认为是：',
        options: [
          { label: '现实、务实的人', val: 'S' },
          { label: '有想象力、有创意的人', val: 'N' },
        ],
      },
      {
        title: '你更喜欢哪种类型的书或电影？',
        options: [
          { label: '基于真实事件、细节丰富', val: 'S' },
          { label: '充满奇幻、探讨深层意义', val: 'N' },
        ],
      },
      {
        title: '你倾向于关注：',
        options: [
          { label: '树木（细节）', val: 'S' },
          { label: '森林（整体）', val: 'N' },
        ],
      },

      // T/F
      {
        title: '在做决定时，你更依赖：',
        options: [
          { label: '逻辑和客观分析', val: 'T' },
          { label: '个人价值观和情感', val: 'F' },
        ],
      },
      {
        title: '你认为更高的赞美是：',
        options: [
          { label: '你很讲道理、很理性', val: 'T' },
          { label: '你很体贴、很有同情心', val: 'F' },
        ],
      },
      {
        title: '在处理冲突时，你倾向于：',
        options: [
          { label: '寻找公平公正的解决方案', val: 'T' },
          { label: '照顾到每个人的感受', val: 'F' },
        ],
      },
      {
        title: '你更容易被哪种人吸引？',
        options: [
          { label: '聪明、有逻辑的人', val: 'T' },
          { label: '热情、有同理心的人', val: 'F' },
        ],
      },
      {
        title: '你更看重：',
        options: [
          { label: '真理和公正', val: 'T' },
          { label: '和谐与人际关系', val: 'F' },
        ],
      },
      {
        title: '当你犯错时，你希望别人：',
        options: [
          { label: '直接指出错误并分析原因', val: 'T' },
          { label: '委婉地提醒并照顾你的面子', val: 'F' },
        ],
      },
      {
        title: '你通常基于什么来评判事物？',
        options: [
          { label: '客观标准和原则', val: 'T' },
          { label: '主观感受和影响', val: 'F' },
        ],
      },

      // J/P
      {
        title: '你的生活方式更倾向于：',
        options: [
          { label: '有计划、有条理', val: 'J' },
          { label: '灵活、随性', val: 'P' },
        ],
      },
      {
        title: '在截止日期前完成任务，你通常：',
        options: [
          { label: '提前完成，避免最后时刻的压力', val: 'J' },
          { label: '在最后期限的压力下爆发灵感完成', val: 'P' },
        ],
      },
      {
        title: '你更喜欢：',
        options: [
          { label: '明确的计划和时间表', val: 'J' },
          { label: '开放的选择和突发的安排', val: 'P' },
        ],
      },
      {
        title: '你的工作空间通常是：',
        options: [
          { label: '整洁有序、物品归位', val: 'J' },
          { label: '有些凌乱，但你知道东西在哪', val: 'P' },
        ],
      },
      {
        title: '在旅行前，你会：',
        options: [
          { label: '制定详细的行程计划', val: 'J' },
          { label: '定个大概方向，边走边看', val: 'P' },
        ],
      },
      {
        title: '你认为哪种状态更让你舒适？',
        options: [
          { label: '事情已经决定和解决', val: 'J' },
          { label: '事情还有改变的余地', val: 'P' },
        ],
      },
      {
        title: '你更看重：',
        options: [
          { label: '结果和按时完成', val: 'J' },
          { label: '过程和体验', val: 'P' },
        ],
      },
    ],
  },
  {
    id: 'MentalAge',
    icon: 'assessment',
    title: '心理年龄测试',
    desc: '15道题，测测你的心理年龄究竟是老成持重还是永远年轻。',
    type: 'age',
    questions: [
      {
        title: '休息日你更喜欢做什么？',
        options: [
          { label: '去游乐园或看动漫', val: 1 },
          { label: '逛街购物或和朋友聚会', val: 3 },
          { label: '在家喝茶看书或去钓鱼', val: 5 },
        ],
      },
      {
        title: '看到喜欢的东西但很贵，你会？',
        options: [
          { label: '不管怎样先买了再说', val: 1 },
          { label: '纠结很久，可能等打折再买', val: 3 },
          { label: '理性分析是否真的需要', val: 5 },
        ],
      },
      {
        title: '遇到不开心的事情，你通常会？',
        options: [
          { label: '大哭一场或发脾气', val: 1 },
          { label: '找朋友倾诉', val: 3 },
          { label: '自己默默消化，理性解决', val: 5 },
        ],
      },
      {
        title: '你对现在流行的网络用语了解多少？',
        options: [
          { label: '了如指掌，经常使用', val: 1 },
          { label: '知道一些常见的', val: 3 },
          { label: '完全不了解或不感兴趣', val: 5 },
        ],
      },
      {
        title: '你更喜欢哪种穿衣风格？',
        options: [
          { label: '色彩鲜艳、个性张扬', val: 1 },
          { label: '跟随潮流、时尚百搭', val: 3 },
          { label: '舒适为主、颜色素雅', val: 5 },
        ],
      },
      {
        title: '对于未来，你最看重什么？',
        options: [
          { label: '好玩和有趣', val: 1 },
          { label: '事业和爱情双丰收', val: 3 },
          { label: '稳定和平安', val: 5 },
        ],
      },
      {
        title: '和长辈聊天时，你通常：',
        options: [
          { label: '觉得有代沟，不想多说', val: 1 },
          { label: '能聊一些，但有时会有分歧', val: 3 },
          { label: '很聊得来，能理解他们的想法', val: 5 },
        ],
      },
      {
        title: '你喜欢看什么类型的电影/电视？',
        options: [
          { label: '动画片、超级英雄片', val: 1 },
          { label: '爱情片、喜剧片', val: 3 },
          { label: '纪录片、历史剧、家庭伦理剧', val: 5 },
        ],
      },
      {
        title: '对于金钱的态度，你是：',
        options: [
          { label: '有多少花多少', val: 1 },
          { label: '会有计划地存一部分', val: 3 },
          { label: '非常注重储蓄和理财', val: 5 },
        ],
      },
      {
        title: '你的朋友圈/空间主要发些什么？',
        options: [
          { label: '每天的心情、吃喝玩乐', val: 1 },
          { label: '偶尔发发生活感悟或风景', val: 3 },
          { label: '很少发或只转发一些有用的文章', val: 5 },
        ],
      },
      {
        title: '遇到不同意见时，你会：',
        options: [
          { label: '坚持己见，甚至争吵', val: 1 },
          { label: '试图说服对方，但也愿意听听', val: 3 },
          { label: '求同存异，不强求一致', val: 5 },
        ],
      },
      {
        title: '你觉得自己的责任感如何？',
        options: [
          { label: '不太想承担责任', val: 1 },
          { label: '该承担的会承担', val: 3 },
          { label: '非常有责任感，经常照顾别人', val: 5 },
        ],
      },
      {
        title: '对于养生，你的态度是：',
        options: [
          { label: '那是老人的事，我还年轻', val: 1 },
          { label: '偶尔会注意一下', val: 3 },
          { label: '非常注重，保温杯里泡枸杞', val: 5 },
        ],
      },
      {
        title: '你更喜欢和什么样的人交朋友？',
        options: [
          { label: '能玩到一起的', val: 1 },
          { label: '有共同语言和爱好的', val: 3 },
          { label: '能互相帮助、成熟稳重的', val: 5 },
        ],
      },
      {
        title: '回首过去，你通常会：',
        options: [
          { label: '很少想过去，只看现在', val: 1 },
          { label: '偶尔怀念美好的时光', val: 3 },
          { label: '经常反思过去的经验教训', val: 5 },
        ],
      },
    ],
  },
]
