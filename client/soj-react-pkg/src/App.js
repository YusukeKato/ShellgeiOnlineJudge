import black_tree_icon from './BlackTreeIcon.jpg';
import './App.css';

const App = () => {
  const blog_url = "https://yusukekato.jp"
  return (
    <div className="App">
      <header className="App-header">
        <img src={black_tree_icon} className="App-logo" alt="logo" />
        <p>
          Edit <code>src/App.js</code> and save to reload.
        </p>
        <a
          className="App-link"
          href="https://reactjs.org"
          target="_blank"
          rel="noopener noreferrer"
        >
          Learn React
        </a>
      </header>
    </div>
  );
}

export default App;
