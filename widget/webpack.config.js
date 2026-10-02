const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = (env, argv) => {
  const isDevelopment = argv.mode === 'development';
  
  return {
    entry: './src/index.ts',
    output: {
      path: path.resolve(__dirname, 'dist'),
      filename: 'askdocs-widget.js',
      library: 'AskDocsWidget',
      libraryTarget: 'umd',
      clean: true,
    },
    resolve: {
      extensions: ['.ts', '.js'],
    },
    module: {
      rules: [
        {
          test: /\.tsx?$/,
          use: 'ts-loader',
          exclude: /node_modules/,
        },
        {
          test: /\.css$/i,
          use: ['style-loader', 'css-loader'],
        },
      ],
    },
    plugins: [
      new HtmlWebpackPlugin({
        template: './src/demo.html',
        filename: 'demo.html',
      }),
    ],
    devServer: {
      static: './dist',
      port: 3001,
      open: true,
    },
    optimization: {
      minimize: !isDevelopment,
    },
    devtool: isDevelopment ? 'source-map' : false,
  };
};