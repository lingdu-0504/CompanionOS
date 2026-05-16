/**
 * 小说创作工作台视图
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Card,
  List,
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
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  BookOutlined,
  RocketOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { NovelProject, NovelChapter, GenerationResult } from '../types/novel';
import { novelApi } from '../services/novelApi';
import './NovelView.css';

const { Content, Sider } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

// 小说类型选项
const GENRE_OPTIONS = [
  { value: 'fantasy', label: '奇幻玄幻' },
  { value: 'xianxia', label: '仙侠修真' },
  { value: 'romance', label: '都市言情' },
  { value: 'scifi', label: '科幻末世' },
  { value: 'history', label: '历史军事' },
  { value: 'game', label: '游戏竞技' },
];

const NovelView: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState<NovelProject[]>([]);
  const [selectedProject, setSelectedProject] = useState<NovelProject | null>(null);
  const [chapters, setChapters] = useState<NovelChapter[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<NovelChapter | null>(null);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [generateModalVisible, setGenerateModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [generateForm] = Form.useForm();
  const [generating, setGenerating] = useState(false);

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

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // 加载项目章节
  const loadChapters = useCallback(async (projectId: string) => {
    try {
      const data = await novelApi.getChapters(projectId);
      setChapters(data);
    } catch (error) {
      message.error('加载章节列表失败');
    }
  }, []);

  // 选择项目
  const handleSelectProject = useCallback((project: NovelProject) => {
    setSelectedProject(project);
    loadChapters(project.id);
    setSelectedChapter(null);
  }, [loadChapters]);

  // 创建项目
  const handleCreateProject = useCallback(async (values: any) => {
    try {
      const newProject = await novelApi.createProject(values);
      setProjects(prev => [...prev, newProject]);
      setCreateModalVisible(false);
      form.resetFields();
      message.success('项目创建成功');
    } catch (error) {
      message.error('项目创建失败');
    }
  }, [form]);

  // 生成章节
  const handleGenerateChapter = useCallback(async (values: any) => {
    if (!selectedProject) return;

    setGenerating(true);
    try {
      const result: GenerationResult = await novelApi.generateChapter(selectedProject.id, values);
      
      if (result.success) {
        message.success('章节生成成功');
        setGenerateModalVisible(false);
        generateForm.resetFields();
        // 刷新章节列表
        await loadChapters(selectedProject.id);
        // 刷新项目信息
        await loadProjects();
      }
    } catch (error) {
      message.error('章节生成失败');
    } finally {
      setGenerating(false);
    }
  }, [selectedProject, generateForm, loadChapters, loadProjects]);

  return (
    <div className="novel-view">
      <Layout className="novel-layout">
        {/* 左侧项目列表 */}
        <Sider width={300} className="novel-sider">
          <div className="sider-header">
            <Title level={4}>小说项目</Title>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
            >
              新建
            </Button>
          </div>

          <List
            dataSource={projects}
            loading={loading}
            renderItem={project => (
              <List.Item
                className={`project-item ${selectedProject?.id === project.id ? 'active' : ''}`}
                onClick={() => handleSelectProject(project)}
              >
                <div className="project-item-content">
                  <div className="project-title">
                    <BookOutlined className="project-icon" />
                    <Text strong>{project.name}</Text>
                  </div>
                  <div className="project-meta">
                    <Tag color="blue">{project.genre}</Tag>
                    <Text type="secondary" className="project-progress">
                      进度: {Math.round(project.progress)}%
                    </Text>
                  </div>
                  <Progress
                    percent={Math.round(project.progress)}
                    size="small"
                    showInfo={false}
                    strokeColor="#52c41a"
                  />
                </div>
              </List.Item>
            )}
          />
        </Sider>

        {/* 右侧内容区 */}
        <Content className="novel-content">
          {selectedProject ? (
            <div className="project-detail">
              {/* 项目头部 */}
              <div className="project-header">
                <div>
                  <Title level={2}>{selectedProject.name}</Title>
                  <Text type="secondary">{selectedProject.description}</Text>
                </div>
                <Space>
                  <Button
                    type="primary"
                    icon={<RocketOutlined />}
                    onClick={() => setGenerateModalVisible(true)}
                  >
                    生成章节
                  </Button>
                </Space>
              </div>

              {/* 项目统计 */}
              <div className="project-stats">
                <Card className="stat-card">
                  <div className="stat-value">{selectedProject.chapter_count}</div>
                  <div className="stat-label">章节数</div>
                </Card>
                <Card className="stat-card">
                  <div className="stat-value">
                    {(selectedProject.current_word_count / 10000).toFixed(1)}万
                  </div>
                  <div className="stat-label">总字数</div>
                </Card>
                <Card className="stat-card">
                  <div className="stat-value">
                    {(selectedProject.target_word_count / 10000).toFixed(1)}万
                  </div>
                  <div className="stat-label">目标字数</div>
                </Card>
                <Card className="stat-card">
                  <div className="stat-value">{Math.round(selectedProject.progress)}%</div>
                  <div className="stat-label">完成进度</div>
                </Card>
              </div>

              {/* 章节列表和编辑区 */}
              <Tabs defaultActiveKey="chapters" className="novel-tabs">
                <TabPane tab="章节列表" key="chapters">
                  <List
                    dataSource={chapters}
                    renderItem={chapter => (
                      <List.Item
                        className={`chapter-item ${selectedChapter?.id === chapter.id ? 'active' : ''}`}
                        onClick={() => setSelectedChapter(chapter)}
                        actions={[
                          <Button icon={<EditOutlined />} size="small">编辑</Button>,
                        ]}
                      >
                        <List.Item.Meta
                          title={`第${chapter.number}章：${chapter.title}`}
                          description={
                            <Space>
                              <Text type="secondary">{chapter.word_count} 字</Text>
                              <Tag color={
                                chapter.status === 'published' ? 'green' :
                                chapter.status === 'reviewing' ? 'orange' : 'default'
                              }>
                                {chapter.status === 'published' ? '已发布' :
                                 chapter.status === 'reviewing' ? '审核中' : '草稿'}
                              </Tag>
                              <Text type="secondary">{new Date(chapter.updated_at).toLocaleString()}</Text>
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                </TabPane>
                <TabPane tab="项目设置" key="settings">
                  <Card>
                    <Text type="secondary">项目设置功能开发中...</Text>
                  </Card>
                </TabPane>
              </Tabs>
            </div>
          ) : (
            <div className="empty-state">
              <BookOutlined className="empty-icon" />
              <Title level={4}>选择或创建小说项目</Title>
              <Text type="secondary">从左侧选择一个项目开始创作</Text>
            </div>
          )}
        </Content>
      </Layout>

      {/* 创建项目弹窗 */}
      <Modal
        title="创建新项目"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleCreateProject}>
          <Form.Item
            label="小说名称"
            name="name"
            rules={[{ required: true, message: '请输入小说名称' }]}
          >
            <Input placeholder="例如：斗破苍穹" />
          </Form.Item>
          <Form.Item label="小说简介" name="description">
            <TextArea rows={4} placeholder="描述你的小说..." />
          </Form.Item>
          <Form.Item
            label="小说类型"
            name="genre"
            initialValue="fantasy"
          >
            <Select>
              {GENRE_OPTIONS.map(opt => (
                <Option key={opt.value} value={opt.value}>{opt.label}</Option>
              ))}
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
              formatter={value => `${value} 字`}
              parser={value => value?.replace(/\s?字/g, '')}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">创建</Button>
              <Button onClick={() => setCreateModalVisible(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 生成章节弹窗 */}
      <Modal
        title="生成新章节"
        open={generateModalVisible}
        onCancel={() => setGenerateModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form form={generateForm} layout="vertical" onFinish={handleGenerateChapter}>
          <Form.Item
            label="章节编号"
            name="chapter_number"
            initialValue={(selectedProject?.chapter_count || 0) + 1}
            rules={[{ required: true, message: '请输入章节编号' }]}
          >
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            label="章节标题"
            name="title"
            rules={[{ required: true, message: '请输入章节标题' }]}
          >
            <Input placeholder="例如：第一章 陨落的天才" />
          </Form.Item>
          <Form.Item
            label="目标字数"
            name="target_words"
            initialValue={3000}
            rules={[{ required: true, message: '请输入目标字数' }]}
          >
            <InputNumber
              min={500}
              step={500}
              formatter={value => `${value} 字`}
              parser={value => value?.replace(/\s?字/g, '')}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                icon={<RocketOutlined />}
                loading={generating}
              >
                {generating ? '生成中...' : '开始生成'}
              </Button>
              <Button onClick={() => setGenerateModalVisible(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default NovelView;

