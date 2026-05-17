/**
 * 小说创作工作台 - 科幻风格
 * Novel Writing Workbench - Sci-Fi Theme
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Layout,
  Card,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Typography,
  Progress,
  Tag,
  Tabs,
  message,
  Spin,
  Badge,
  Tooltip,
  Divider,
  Statistic,
  Row,
  Col,
  Timeline,
  Avatar,
  List,
  Dropdown,
  Switch,
  Slider,
  Alert,
  notification,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  BookOutlined,
  RocketOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  SettingOutlined,
  CloudUploadOutlined,
  TeamOutlined,
  FileTextOutlined,
  BarChartOutlined,
  ThunderboltOutlined,
  CalendarOutlined,
  GlobalOutlined,
  SyncOutlined,
  EyeOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import type { NovelProject, NovelChapter, GenerationResult } from '../types/novel';
import { novelApi } from '../services/novelApi';
import './NovelView.css';

const { Content, Sider } = Layout;
const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

interface Task {
  id: string;
  type: string;
  status: string;
  created_at: string;
  result?: any;
}

interface Platform {
  id: string;
  name: string;
  status: string;
  lastPublish?: string;
}

const NovelView: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [projects, setProjects] = useState<NovelProject[]>([]);
  const [selectedProject, setSelectedProject] = useState<NovelProject | null>(null);
  const [chapters, setChapters] = useState<NovelChapter[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<NovelChapter | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [generateModalVisible, setGenerateModalVisible] = useState(false);
  const [settingsModalVisible, setSettingsModalVisible] = useState(false);
  const [publishModalVisible, setPublishModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [generateForm] = Form.useForm();
  const [settingsForm] = Form.useForm();
  const [publishForm] = Form.useForm();

  // 统计数据
  const stats = useMemo(() => {
    if (!selectedProject) return null;
    return {
      totalWords: selectedProject.current_word_count,
      targetWords: selectedProject.target_word_count,
      chapterCount: selectedProject.chapter_count,
      progress: selectedProject.progress,
      avgWordsPerChapter: selectedProject.chapter_count > 0 
        ? Math.round(selectedProject.current_word_count / selectedProject.chapter_count) 
        : 0,
    };
  }, [selectedProject]);

  // 加载项目列表
  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await novelApi.getProjects();
      setProjects(data);
    } catch (error) {
      message.error('加载项目列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  // 加载项目章节
  const loadChapters = useCallback(async (projectId: string) => {
    try {
      const data = await novelApi.getChapters(projectId);
      setChapters(data);
    } catch (error) {
      message.error('加载章节列表失败');
    }
  }, []);

  // 加载任务列表
  const loadTasks = useCallback(async (projectId?: string) => {
    try {
      const data = await novelApi.getTasks(projectId);
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    }
  }, []);

  // 加载平台列表
  const loadPlatforms = useCallback(async () => {
    try {
      const data = await novelApi.getPlatforms();
      setPlatforms(data.map(p => ({
        ...p,
        status: 'idle',
      })));
    } catch (error) {
      console.error('Failed to load platforms:', error);
    }
  }, []);

  useEffect(() => {
    loadProjects();
    loadPlatforms();
  }, [loadProjects, loadPlatforms]);

  // 选择项目
  const handleSelectProject = useCallback((project: NovelProject) => {
    setSelectedProject(project);
    loadChapters(project.id);
    loadTasks(project.id);
    setSelectedChapter(null);
  }, [loadChapters, loadTasks]);

  // 创建项目
  const handleCreateProject = useCallback(async (values: any) => {
    try {
      const newProject = await novelApi.createProject(values);
      setProjects(prev => [...prev, newProject]);
      setCreateModalVisible(false);
      form.resetFields();
      message.success('✨ 项目创建成功');
      notification.success({
        message: '创作空间已就绪',
        description: `《${newProject.name}》已准备好开始创作`,
      });
    } catch (error) {
      message.error('项目创建失败');
    }
  }, [form]);

  // 生成章节
  const handleGenerateChapter = useCallback(async (values: any) => {
    if (!selectedProject) return;

    setGenerating(true);
    try {
      notification.info({
        message: '🚀 开始生成',
        description: `正在创作第${values.chapter_number}章，请稍候...`,
        duration: 0,
      });

      const result: GenerationResult = await novelApi.generateChapter(
        selectedProject.id, 
        values
      );
      
      notification.destroy();
      
      if (result.success) {
        message.success('✨ 章节生成成功');
        notification.success({
          message: '创作完成',
          description: `《${selectedProject.name}》第${values.chapter_number}章已生成`,
        });
        setGenerateModalVisible(false);
        generateForm.resetFields();
        await loadChapters(selectedProject.id);
        await loadProjects();
      }
    } catch (error) {
      notification.destroy();
      message.error('章节生成失败');
    } finally {
      setGenerating(false);
    }
  }, [selectedProject, generateForm, loadChapters, loadProjects]);

  // 发布章节
  const handlePublishChapter = useCallback(async (values: any) => {
    if (!selectedProject) return;

    try {
      notification.info({
        message: '📤 开始发布',
        description: '正在模拟发布流程...',
        duration: 0,
      });

      await new Promise(resolve => setTimeout(resolve, 2000));

      notification.destroy();
      message.success('✨ 发布成功');
      setPublishModalVisible(false);
      publishForm.resetFields();
    } catch (error) {
      notification.destroy();
      message.error('发布失败');
    }
  }, [selectedProject, publishForm]);

  // 获取状态颜色
  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      draft: '#6b7280',
      reviewing: '#f59e0b',
      published: '#10b981',
      generating: '#3b82f6',
    };
    return colors[status] || '#6b7280';
  };

  // 获取任务状态图标
  const getTaskIcon = (status: string) => {
    switch (status) {
      case 'running': return <LoadingOutlined spin />;
      case 'completed': return <CheckCircleOutlined />;
      case 'failed': return <DeleteOutlined />;
      default: return <ClockCircleOutlined />;
    }
  };

  return (
    <div className="novel-view sci-fi-theme">
      {/* 背景效果 */}
      <div className="grid-bg" />
      <div className="glow-orb orb-1" />
      <div className="glow-orb orb-2" />

      <Layout className="novel-layout">
        {/* 左侧项目列表 */}
        <Sider width={320} className="novel-sider glass">
          <div className="sider-header">
            <div className="header-title">
              <RocketOutlined className="header-icon" />
              <Title level={4} className="gradient-text">创作中心</Title>
            </div>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
              className="glow-button"
            >
              新建
            </Button>
          </div>

          <div className="project-list">
            <Spin spinning={loading}>
              {projects.length === 0 ? (
                <div className="empty-state">
                  <BookOutlined className="empty-icon" />
                  <Text type="secondary">暂无项目</Text>
                  <Button 
                    type="link" 
                    onClick={() => setCreateModalVisible(true)}
                    className="create-link"
                  >
                    创建第一个项目
                  </Button>
                </div>
              ) : (
                projects.map(project => (
                  <div
                    key={project.id}
                    className={`project-item ${selectedProject?.id === project.id ? 'active' : ''}`}
                    onClick={() => handleSelectProject(project)}
                  >
                    <div className="project-header">
                      <BookOutlined className="project-icon" />
                      <Text strong className="project-name">{project.name}</Text>
                    </div>
                    <div className="project-meta">
                      <Tag color="blue" className="genre-tag">{project.genre}</Tag>
                      <Text type="secondary" className="progress-text">
                        {Math.round(project.progress)}%
                      </Text>
                    </div>
                    <Progress
                      percent={Math.round(project.progress)}
                      size="small"
                      showInfo={false}
                      strokeColor={{
                        '0%': '#6366f1',
                        '100%': '#06b6d4',
                      }}
                    />
                  </div>
                ))
              )}
            </Spin>
          </div>

          {/* 快捷操作 */}
          <div className="quick-actions">
            <Divider className="divider" />
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button 
                block 
                icon={<SettingOutlined />}
                onClick={() => setSettingsModalVisible(true)}
                className="action-button"
              >
                全局设置
              </Button>
            </Space>
          </div>
        </Sider>

        {/* 右侧内容区 */}
        <Content className="novel-content">
          {selectedProject ? (
            <div className="project-detail">
              {/* 项目头部 */}
              <div className="project-header animate-fadeIn">
                <div className="project-info">
                  <Title level={2} className="gradient-text">{selectedProject.name}</Title>
                  <Paragraph className="description">{selectedProject.description}</Paragraph>
                </div>
                <Space size="middle">
                  <Button
                    type="primary"
                    icon={<RocketOutlined />}
                    onClick={() => setGenerateModalVisible(true)}
                    className="glow-button"
                    size="large"
                  >
                    开始创作
                  </Button>
                  <Button
                    icon={<CloudUploadOutlined />}
                    onClick={() => setPublishModalVisible(true)}
                    size="large"
                  >
                    发布
                  </Button>
                </Space>
              </div>

              {/* 统计卡片 */}
              <Row gutter={[16, 16]} className="stats-row animate-fadeIn">
                <Col xs={12} sm={6}>
                  <Card className="stat-card">
                    <Statistic
                      title="总字数"
                      value={stats?.totalWords || 0}
                      suffix="字"
                      valueStyle={{ 
                        color: '#6366f1',
                        fontFamily: 'var(--mono)',
                      }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={6}>
                  <Card className="stat-card">
                    <Statistic
                      title="章节数"
                      value={stats?.chapterCount || 0}
                      suffix="章"
                      valueStyle={{ 
                        color: '#06b6d4',
                        fontFamily: 'var(--mono)',
                      }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={6}>
                  <Card className="stat-card">
                    <Statistic
                      title="平均章节"
                      value={stats?.avgWordsPerChapter || 0}
                      suffix="字"
                      valueStyle={{ 
                        color: '#10b981',
                        fontFamily: 'var(--mono)',
                      }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={6}>
                  <Card className="stat-card">
                    <Statistic
                      title="完成进度"
                      value={stats?.progress || 0}
                      suffix="%"
                      valueStyle={{ 
                        color: '#f59e0b',
                        fontFamily: 'var(--mono)',
                      }}
                    />
                    <Progress 
                      percent={Math.round(stats?.progress || 0)} 
                      showInfo={false}
                      strokeColor={{
                        '0%': '#6366f1',
                        '100%': '#06b6d4',
                      }}
                      className="progress-bar"
                    />
                  </Card>
                </Col>
              </Row>

              {/* 标签页 */}
              <Tabs defaultActiveKey="chapters" className="novel-tabs animate-fadeIn">
                <TabPane 
                  tab={
                    <span className="tab-title">
                      <FileTextOutlined /> 章节列表
                    </span>
                  } 
                  key="chapters"
                >
                  <div className="chapters-section">
                    <List
                      dataSource={chapters}
                      renderItem={(chapter, index) => (
                        <List.Item
                          className={`chapter-item ${selectedChapter?.id === chapter.id ? 'active' : ''}`}
                          onClick={() => setSelectedChapter(chapter)}
                          actions={[
                            <Button 
                              key="edit" 
                              icon={<EditOutlined />} 
                              size="small"
                              className="chapter-action"
                            >
                              编辑
                            </Button>,
                          ]}
                        >
                          <List.Item.Meta
                            avatar={
                              <Badge 
                                count={chapter.number} 
                                style={{ 
                                  backgroundColor: getStatusColor(chapter.status),
                                  fontFamily: 'var(--mono)',
                                }}
                              />
                            }
                            title={
                              <Text strong className="chapter-title">
                                {chapter.title}
                              </Text>
                            }
                            description={
                              <Space>
                                <Text type="secondary" className="chapter-meta">
                                  {chapter.word_count} 字
                                </Text>
                                <Tag 
                                  color={chapter.status === 'published' ? 'green' : 'default'}
                                  className="status-tag"
                                >
                                  {chapter.status === 'published' ? '已发布' : 
                                   chapter.status === 'reviewing' ? '审核中' : '草稿'}
                                </Tag>
                                <Text type="secondary" className="chapter-date">
                                  {new Date(chapter.updated_at).toLocaleDateString()}
                                </Text>
                              </Space>
                            }
                          />
                        </List.Item>
                      )}
                      locale={{ emptyText: '暂无章节，点击"开始创作"生成第一章' }}
                    />
                  </div>
                </TabPane>

                <TabPane 
                  tab={
                    <span className="tab-title">
                      <ThunderboltOutlined /> 创作任务
                    </span>
                  } 
                  key="tasks"
                >
                  <div className="tasks-section">
                    <List
                      dataSource={tasks}
                      renderItem={task => (
                        <List.Item className="task-item">
                          <List.Item.Meta
                            avatar={getTaskIcon(task.status)}
                            title={`任务: ${task.type}`}
                            description={
                              <Space>
                                <Tag color={
                                  task.status === 'completed' ? 'green' :
                                  task.status === 'failed' ? 'red' : 'blue'
                                }>
                                  {task.status}
                                </Tag>
                                <Text type="secondary">
                                  {new Date(task.created_at).toLocaleString()}
                                </Text>
                              </Space>
                            }
                          />
                        </List.Item>
                      )}
                      locale={{ emptyText: '暂无任务' }}
                    />
                  </div>
                </TabPane>

                <TabPane 
                  tab={
                    <span className="tab-title">
                      <GlobalOutlined /> 发布平台
                    </span>
                  } 
                  key="platforms"
                >
                  <div className="platforms-section">
                    <List
                      grid={{ gutter: 16, xs: 1, sm: 2, md: 3 }}
                      dataSource={platforms}
                      renderItem={platform => (
                        <List.Item>
                          <Card className="platform-card">
                            <div className="platform-header">
                              <GlobalOutlined className="platform-icon" />
                              <Text strong>{platform.name}</Text>
                            </div>
                            <div className="platform-status">
                              <Badge 
                                status={platform.status === 'idle' ? 'default' : 'processing'} 
                                text={platform.status === 'idle' ? '未连接' : '连接中'} 
                              />
                            </div>
                            <div className="platform-actions">
                              <Button size="small" type="primary" className="glow-button">
                                配置
                              </Button>
                            </div>
                          </Card>
                        </List.Item>
                      )}
                    />
                  </div>
                </TabPane>
              </Tabs>

              {/* 章节预览 */}
              {selectedChapter && (
                <Card 
                  className="chapter-preview animate-scaleIn"
                  title={
                    <Space>
                      <FileTextOutlined />
                      <span>{selectedChapter.title}</span>
                    </Space>
                  }
                  extra={
                    <Button 
                      icon={<EyeOutlined />}
                      onClick={() => {
                        Modal.info({
                          title: selectedChapter.title,
                          content: (
                            <div style={{ maxHeight: '60vh', overflow: 'auto' }}>
                              {selectedChapter.content}
                            </div>
                          ),
                          width: 800,
                        });
                      }}
                    >
                      预览
                    </Button>
                  }
                >
                  <Paragraph className="chapter-content">
                    {selectedChapter.content.slice(0, 500)}
                    {selectedChapter.content.length > 500 && '...'}
                  </Paragraph>
                </Card>
              )}
            </div>
          ) : (
            <div className="empty-state-full animate-fadeIn">
              <div className="glow-orb orb-center" />
              <RocketOutlined className="empty-icon-large" />
              <Title level={3} className="gradient-text">欢迎使用AI小说创作系统</Title>
              <Paragraph type="secondary" className="empty-description">
                从左侧选择一个项目开始创作，或创建新项目
              </Paragraph>
              <Space>
                <Button 
                  type="primary" 
                  size="large"
                  icon={<PlusOutlined />}
                  onClick={() => setCreateModalVisible(true)}
                  className="glow-button"
                >
                  创建新项目
                </Button>
                <Button size="large" icon={<BookOutlined />}>
                  查看示例
                </Button>
              </Space>
            </div>
          )}
        </Content>
      </Layout>

      {/* 创建项目弹窗 */}
      <Modal
        title={
          <Space>
            <BookOutlined />
            <span>创建新项目</span>
          </Space>
        }
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        footer={null}
        width={600}
        className="sci-fi-modal"
      >
        <Form form={form} layout="vertical" onFinish={handleCreateProject}>
          <Form.Item
            label="小说名称"
            name="name"
            rules={[{ required: true, message: '请输入小说名称' }]}
          >
            <Input placeholder="例如：星河传奇" size="large" />
          </Form.Item>
          <Form.Item label="小说简介" name="description">
            <TextArea rows={3} placeholder="描述你的小说..." />
          </Form.Item>
          <Form.Item
            label="小说类型"
            name="genre"
            initialValue="fantasy"
          >
            <Select size="large">
              <Option value="fantasy">玄幻奇幻</Option>
              <Option value="xianxia">仙侠修真</Option>
              <Option value="romance">都市言情</Option>
              <Option value="scifi">科幻末世</Option>
              <Option value="martial_arts">武侠仙侠</Option>
              <Option value="urban">都市异能</Option>
            </Select>
          </Form.Item>
          <Form.Item
            label="目标字数"
            name="target_word_count"
            initialValue={1000000}
          >
            <InputNumber
              min={10000}
              step={10000}
              style={{ width: '100%' }}
              size="large"
              formatter={value => `${(value / 10000).toFixed(0)}万字`}
              parser={value => parseFloat(value?.replace(/万字/g, '')) * 10000 || 0}
            />
          </Form.Item>
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setCreateModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" className="glow-button">
                创建项目
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 生成章节弹窗 */}
      <Modal
        title={
          <Space>
            <RocketOutlined />
            <span>开始创作</span>
          </Space>
        }
        open={generateModalVisible}
        onCancel={() => setGenerateModalVisible(false)}
        footer={null}
        width={600}
        className="sci-fi-modal"
        maskClosable={generating}
        closable={!generating}
      >
        <Spin spinning={generating} tip="✨ 正在创作中，请稍候...">
          <Form form={generateForm} layout="vertical" onFinish={handleGenerateChapter}>
            <Form.Item
              label="章节编号"
              name="chapter_number"
              initialValue={(selectedProject?.chapter_count || 0) + 1}
              rules={[{ required: true, message: '请输入章节编号' }]}
            >
              <InputNumber min={1} style={{ width: '100%' }} size="large" />
            </Form.Item>
            <Form.Item
              label="章节标题"
              name="title"
              rules={[{ required: true, message: '请输入章节标题' }]}
            >
              <Input placeholder="例如：第一章 星辰降临" size="large" />
            </Form.Item>
            <Form.Item
              label="目标字数"
              name="target_words"
              initialValue={3000}
              rules={[{ required: true, message: '请输入目标字数' }]}
            >
              <Slider
                min={1000}
                max={10000}
                step={500}
                marks={{
                  1000: '1k',
                  3000: '3k',
                  5000: '5k',
                  10000: '1万',
                }}
              />
            </Form.Item>
            <Alert
              message="创作提示"
              description="系统将根据您的小说类型和叙事结构，生成符合上下文的内容。生成过程可能需要数秒到数十秒。"
              type="info"
              showIcon
              className="generation-tip"
            />
            <Form.Item>
              <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                <Button onClick={() => setGenerateModalVisible(false)} disabled={generating}>
                  取消
                </Button>
                <Button 
                  type="primary" 
                  htmlType="submit" 
                  className="glow-button"
                  loading={generating}
                  icon={<RocketOutlined />}
                  size="large"
                >
                  {generating ? '创作中...' : '开始创作'}
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Spin>
      </Modal>

      {/* 发布弹窗 */}
      <Modal
        title={
          <Space>
            <CloudUploadOutlined />
            <span>发布章节</span>
          </Space>
        }
        open={publishModalVisible}
        onCancel={() => setPublishModalVisible(false)}
        footer={null}
        width={500}
        className="sci-fi-modal"
      >
        <Form form={publishForm} layout="vertical" onFinish={handlePublishChapter}>
          <Form.Item
            label="选择章节"
            name="chapter_number"
            rules={[{ required: true }]}
          >
            <Select placeholder="选择要发布的章节" size="large">
              {chapters.map(c => (
                <Option key={c.number} value={c.number}>
                  第{c.number}章：{c.title}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            label="发布平台"
            name="platform"
            initialValue="qidian"
          >
            <Select size="large">
              <Option value="qidian">起点中文网</Option>
              <Option value="zongheng">纵横中文网</Option>
              <Option value="17k">17K小说网</Option>
              <Option value="jjwxc">晋江文学城</Option>
              <Option value="changpei">长佩文学</Option>
            </Select>
          </Form.Item>
          <Alert
            message="发布说明"
            description="发布将自动模拟人类输入方式，定时定量更新内容。"
            type="info"
            showIcon
            className="publish-tip"
          />
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setPublishModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" className="glow-button">
                开始发布
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 设置弹窗 */}
      <Modal
        title={
          <Space>
            <SettingOutlined />
            <span>全局设置</span>
          </Space>
        }
        open={settingsModalVisible}
        onCancel={() => setSettingsModalVisible(false)}
        footer={null}
        width={600}
        className="sci-fi-modal"
      >
        <Form form={settingsForm} layout="vertical">
          <Form.Item label="默认章节字数">
            <InputNumber
              min={1000}
              max={10000}
              defaultValue={3000}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item label="自动保存">
            <Switch defaultChecked />
          </Form.Item>
          <Form.Item label="发布延迟（秒）">
            <Slider min={1} max={10} defaultValue={3} />
          </Form.Item>
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setSettingsModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" className="glow-button">
                保存设置
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default NovelView;

